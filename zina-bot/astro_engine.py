#!/usr/bin/env python3
"""
Astro Engine — реальные астрономические расчёты для Зины.
Использует kerykeion (Swiss Ephemeris) и ephem.
"""

from __future__ import annotations

import ephem
from datetime import datetime, timezone
from typing import Optional
import warnings

# Подавляем предупреждения kerykeion о geonames
warnings.filterwarnings("ignore", category=UserWarning)

# ---------------------------------------------------------------------------
# База городов: (lat, lng, tz_str)
# ---------------------------------------------------------------------------
CITIES: dict[str, tuple[float, float, str]] = {
    # Россия
    "москва": (55.75, 37.62, "Europe/Moscow"),
    "moscow": (55.75, 37.62, "Europe/Moscow"),
    "санкт-петербург": (59.95, 30.32, "Europe/Moscow"),
    "петербург": (59.95, 30.32, "Europe/Moscow"),
    "спб": (59.95, 30.32, "Europe/Moscow"),
    "новосибирск": (54.99, 82.90, "Asia/Novosibirsk"),
    "екатеринбург": (56.84, 60.60, "Asia/Yekaterinburg"),
    "красноярск": (56.02, 92.87, "Asia/Krasnoyarsk"),
    "владивосток": (43.12, 131.91, "Asia/Vladivostok"),
    "находка": (42.82, 132.87, "Asia/Vladivostok"),
    "г. находка": (42.82, 132.87, "Asia/Vladivostok"),
    "находка приморский край": (42.82, 132.87, "Asia/Vladivostok"),
    "г. находка, приморский край": (42.82, 132.87, "Asia/Vladivostok"),
    "хабаровск": (48.48, 135.08, "Asia/Vladivostok"),
    "иркутск": (52.30, 104.30, "Asia/Irkutsk"),
    "омск": (54.99, 73.37, "Asia/Omsk"),
    "томск": (56.50, 84.97, "Asia/Tomsk"),
    "тюмень": (57.15, 65.53, "Asia/Yekaterinburg"),
    "казань": (55.79, 49.12, "Europe/Moscow"),
    "нижний новгород": (56.33, 44.00, "Europe/Moscow"),
    "самара": (53.20, 50.15, "Europe/Samara"),
    "уфа": (54.74, 55.97, "Asia/Yekaterinburg"),
    "краснодар": (45.04, 38.98, "Europe/Moscow"),
    "воронеж": (51.67, 39.20, "Europe/Moscow"),
    "ростов-на-дону": (47.23, 39.72, "Europe/Moscow"),
    "пермь": (58.00, 56.25, "Asia/Yekaterinburg"),
    "челябинск": (55.16, 61.40, "Asia/Yekaterinburg"),
    # Украина
    "киев": (50.45, 30.52, "Europe/Kiev"),
    "харьков": (49.99, 36.23, "Europe/Kiev"),
    "одесса": (46.48, 30.74, "Europe/Kiev"),
    "днепр": (48.46, 34.99, "Europe/Kiev"),
    "донецк": (48.00, 37.80, "Europe/Kiev"),
    # Беларусь
    "минск": (53.90, 27.57, "Europe/Minsk"),
    # Казахстан
    "алматы": (43.25, 76.92, "Asia/Almaty"),
    "астана": (51.18, 71.45, "Asia/Almaty"),
    # Мировые
    "лондон": (51.51, -0.13, "Europe/London"),
    "london": (51.51, -0.13, "Europe/London"),
    "paris": (48.85, 2.35, "Europe/Paris"),
    "париж": (48.85, 2.35, "Europe/Paris"),
    "berlin": (52.52, 13.40, "Europe/Berlin"),
    "берлин": (52.52, 13.40, "Europe/Berlin"),
    "new york": (40.71, -74.01, "America/New_York"),
    "нью-йорк": (40.71, -74.01, "America/New_York"),
    "los angeles": (34.05, -118.24, "America/Los_Angeles"),
    "dubai": (25.20, 55.27, "Asia/Dubai"),
    "дубай": (25.20, 55.27, "Asia/Dubai"),
    "istanbul": (41.01, 28.96, "Europe/Istanbul"),
    "стамбул": (41.01, 28.96, "Europe/Istanbul"),
    "bangkok": (13.75, 100.52, "Asia/Bangkok"),
    "бангкок": (13.75, 100.52, "Asia/Bangkok"),
    "tokyo": (35.69, 139.69, "Asia/Tokyo"),
    "токио": (35.69, 139.69, "Asia/Tokyo"),
    "beijing": (39.91, 116.39, "Asia/Shanghai"),
    "пекин": (39.91, 116.39, "Asia/Shanghai"),
}

PLANET_RU = {
    "Sun": "Солнце", "Moon": "Луна", "Mercury": "Меркурий",
    "Venus": "Венера", "Mars": "Марс", "Jupiter": "Юпитер",
    "Saturn": "Сатурн", "Uranus": "Уран", "Neptune": "Нептун",
    "Pluto": "Плутон",
}

SIGN_RU = {
    "Ari": "Овен ♈", "Tau": "Телец ♉", "Gem": "Близнецы ♊",
    "Can": "Рак ♋", "Leo": "Лев ♌", "Vir": "Дева ♍",
    "Lib": "Весы ♎", "Sco": "Скорпион ♏", "Sag": "Стрелец ♐",
    "Cap": "Козерог ♑", "Aqu": "Водолей ♒", "Pis": "Рыбы ♓",
}

MOON_PHASES = [
    (0, 7, "🌑 Новолуние"),
    (7, 14, "🌒 Растущий серп"),
    (14, 21, "🌓 Первая четверть"),
    (21, 40, "🌔 Прибывающая луна"),
    (40, 60, "🌕 Полнолуние"),
    (60, 79, "🌖 Убывающая луна"),
    (79, 86, "🌗 Последняя четверть"),
    (86, 100, "🌘 Убывающий серп"),
]

ASPECT_NAMES = {
    "conjunction": "соединение (0°)",
    "opposition": "оппозиция (180°)",
    "trine": "трин (120°)",
    "square": "квадратура (90°)",
    "sextile": "секстиль (60°)",
}


def _find_city(place: str) -> tuple[float, float, str] | None:
    """Нечёткий поиск города в базе."""
    normalized = place.strip().lower()
    if normalized in CITIES:
        return CITIES[normalized]
    for key, val in CITIES.items():
        if key in normalized or normalized in key:
            return val
    return None


def _parse_date(birth_date: str) -> tuple[int, int, int]:
    """Парсит дату в форматах DD.MM.YYYY или YYYY-MM-DD."""
    birth_date = birth_date.strip()
    if "." in birth_date:
        parts = birth_date.split(".")
        return int(parts[2]), int(parts[1]), int(parts[0])
    elif "-" in birth_date:
        parts = birth_date.split("-")
        return int(parts[0]), int(parts[1]), int(parts[2])
    raise ValueError(f"Unknown date format: {birth_date}")


def _parse_time(birth_time: str) -> tuple[int, int]:
    """Парсит время HH:MM."""
    parts = birth_time.strip().split(":")
    return int(parts[0]), int(parts[1])


def _moon_phase_name(cycle_pct: float) -> str:
    for lo, hi, name in MOON_PHASES:
        if lo <= cycle_pct < hi:
            return name
    return "🌕 Полнолуние"


def _calc_aspect(pos1: float, pos2: float) -> str | None:
    """Определяет аспект между двумя эклиптическими позициями (0–360)."""
    diff = abs(pos1 - pos2) % 360
    if diff > 180:
        diff = 360 - diff
    orbs = [
        (0, 8, "conjunction"),
        (180, 8, "opposition"),
        (120, 7, "trine"),
        (90, 7, "square"),
        (60, 6, "sextile"),
    ]
    for target, orb, name in orbs:
        if abs(diff - target) <= orb:
            return name
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_current_sky() -> str:
    """Текущие позиции планет, фаза луны и ключевые аспекты дня."""
    try:
        now = ephem.now()
        dt_now = datetime.utcnow()

        # Луна
        moon = ephem.Moon(now)
        prev_new = ephem.previous_new_moon(now)
        next_new = ephem.next_new_moon(now)
        cycle_pct = (now - prev_new) / (next_new - prev_new) * 100
        phase_name = _moon_phase_name(cycle_pct)
        next_full = ephem.next_full_moon(now)
        next_full_dt = ephem.Date(next_full).datetime()
        days_to_full = (next_full_dt - dt_now).days

        lines = [
            f"=== ТЕКУЩЕЕ НЕБО ({dt_now.strftime('%d.%m.%Y %H:%M')} UTC) ===",
            f"Луна: {phase_name}, освещённость {moon.moon_phase*100:.0f}%",
            f"До следующего полнолуния: {days_to_full} дн.",
        ]

        # Текущие позиции планет через ephem (эклиптика)
        planets_ephem = {
            "Солнце": ephem.Sun(now),
            "Меркурий": ephem.Mercury(now),
            "Венера": ephem.Venus(now),
            "Марс": ephem.Mars(now),
            "Юпитер": ephem.Jupiter(now),
            "Сатурн": ephem.Saturn(now),
        }

        try:
            from kerykeion import AstrologicalSubject
            # Текущий момент (Москва как центр)
            cur = AstrologicalSubject(
                "Now", dt_now.year, dt_now.month, dt_now.day,
                dt_now.hour, dt_now.minute,
                lat=55.75, lng=37.62, tz_str="UTC", online=False,
            )
            planet_objects = [
                ("Солнце", cur.sun), ("Луна", cur.moon),
                ("Меркурий", cur.mercury), ("Венера", cur.venus),
                ("Марс", cur.mars), ("Юпитер", cur.jupiter),
                ("Сатурн", cur.saturn), ("Уран", cur.uranus),
                ("Нептун", cur.neptune), ("Плутон", cur.pluto),
            ]
            lines.append("\nПланеты сегодня:")
            for pname, p in planet_objects:
                sign = SIGN_RU.get(p.sign, p.sign)
                retro = " ℞" if p.retrograde else ""
                lines.append(f"  {pname}: {sign} {p.position:.1f}°{retro}")

            # Аспекты между текущими планетами (самые значимые)
            aspects_found = []
            planet_pos = [(n, p.abs_pos) for n, p in planet_objects]
            for i in range(len(planet_pos)):
                for j in range(i + 1, len(planet_pos)):
                    n1, pos1 = planet_pos[i]
                    n2, pos2 = planet_pos[j]
                    aspect = _calc_aspect(pos1, pos2)
                    if aspect and aspect in ("conjunction", "opposition", "trine", "square"):
                        aspects_found.append(f"  {n1} — {n2}: {ASPECT_NAMES[aspect]}")

            if aspects_found:
                lines.append("\nАктивные аспекты:")
                lines.extend(aspects_found[:6])  # не больше 6

        except Exception as e:
            # Если kerykeion не работает — используем только ephem данные
            lines.append(f"\n[kerykeion недоступен: {e}]")

        return "\n".join(lines)

    except Exception as e:
        return f"[Астро-движок недоступен: {e}]"


def get_natal_chart(birth_date: str, birth_time: str, birth_place: str) -> str:
    """
    Натальная карта пользователя.
    birth_date: "DD.MM.YYYY" или "YYYY-MM-DD"
    birth_time: "HH:MM"
    birth_place: название города
    """
    try:
        from kerykeion import AstrologicalSubject

        year, month, day = _parse_date(birth_date)
        hour, minute = _parse_time(birth_time)
        city_data = _find_city(birth_place)

        if city_data:
            lat, lng, tz_str = city_data
            subject = AstrologicalSubject(
                "User", year, month, day, hour, minute,
                lat=lat, lng=lng, tz_str=tz_str, online=False,
            )
        else:
            # Фолбэк: Москва если город не найден
            subject = AstrologicalSubject(
                "User", year, month, day, hour, minute,
                lat=55.75, lng=37.62, tz_str="Europe/Moscow", online=False,
            )
            birth_place += " (координаты не найдены, использована Москва)"

        planet_list = [
            ("Солнце", subject.sun), ("Луна", subject.moon),
            ("Меркурий", subject.mercury), ("Венера", subject.venus),
            ("Марс", subject.mars), ("Юпитер", subject.jupiter),
            ("Сатурн", subject.saturn), ("Уран", subject.uranus),
            ("Нептун", subject.neptune), ("Плутон", subject.pluto),
        ]

        lines = [
            f"=== НАТАЛЬНАЯ КАРТА ===",
            f"Дата: {birth_date} {birth_time}, {birth_place}",
            "",
            "Планеты:",
        ]
        for pname, p in planet_list:
            sign = SIGN_RU.get(p.sign, p.sign)
            retro = " ℞" if p.retrograde else ""
            lines.append(f"  {pname}: {sign} {p.position:.1f}° (дом {p.house}){retro}")

        lines.append(f"\nАсцендент: {SIGN_RU.get(subject.first_house.sign, subject.first_house.sign)} {subject.first_house.position:.1f}°")

        # Аспекты натальной карты
        try:
            from kerykeion.aspects import AspectsFactory
            natal_model = subject.model()
            aspects_result = AspectsFactory.natal_aspects(natal_model)
            relevant = [
                a for a in aspects_result.aspects
                if a.aspect_degrees in (0, 60, 90, 120, 180)
                and abs(a.orbit) < 7
            ]
            if relevant:
                lines.append("\nКлючевые аспекты:")
                for a in relevant[:8]:
                    p1 = PLANET_RU.get(a.p1_name, a.p1_name)
                    p2 = PLANET_RU.get(a.p2_name, a.p2_name)
                    lines.append(f"  {p1} — {p2}: {ASPECT_NAMES.get(a.aspect, a.aspect)} (орб {a.orbit:.1f}°)")
        except Exception:
            pass

        return "\n".join(lines)

    except Exception as e:
        return f"[Натальная карта недоступна: {e}]"


def get_transit_context(birth_date: str, birth_time: str, birth_place: str) -> str:
    """
    Транзиты: текущие планеты к натальной карте.
    Возвращает значимые аспекты сегодня.
    """
    try:
        from kerykeion import AstrologicalSubject

        year, month, day = _parse_date(birth_date)
        hour, minute = _parse_time(birth_time)
        city_data = _find_city(birth_place)

        if city_data:
            lat, lng, tz_str = city_data
        else:
            lat, lng, tz_str = 55.75, 37.62, "Europe/Moscow"

        natal = AstrologicalSubject(
            "Natal", year, month, day, hour, minute,
            lat=lat, lng=lng, tz_str=tz_str, online=False,
        )

        dt_now = datetime.utcnow()
        transit = AstrologicalSubject(
            "Transit", dt_now.year, dt_now.month, dt_now.day,
            dt_now.hour, dt_now.minute,
            lat=lat, lng=lng, tz_str="UTC", online=False,
        )

        natal_planets = {
            "Солнце": natal.sun.abs_pos, "Луна": natal.moon.abs_pos,
            "Меркурий": natal.mercury.abs_pos, "Венера": natal.venus.abs_pos,
            "Марс": natal.mars.abs_pos, "Юпитер": natal.jupiter.abs_pos,
            "Сатурн": natal.saturn.abs_pos, "Уран": natal.uranus.abs_pos,
            "Нептун": natal.neptune.abs_pos, "Плутон": natal.pluto.abs_pos,
        }

        transit_planets = [
            ("Солнце", transit.sun), ("Луна", transit.moon),
            ("Меркурий", transit.mercury), ("Венера", transit.venus),
            ("Марс", transit.mars), ("Юпитер", transit.jupiter),
            ("Сатурн", transit.saturn),
        ]

        transits_found = []
        for t_name, t_planet in transit_planets:
            for n_name, n_pos in natal_planets.items():
                aspect = _calc_aspect(t_planet.abs_pos, n_pos)
                if aspect and aspect in ("conjunction", "opposition", "trine", "square"):
                    retro = " ℞" if t_planet.retrograde else ""
                    transits_found.append(
                        f"  {t_name}{retro} → {n_name} натал.: {ASPECT_NAMES[aspect]}"
                    )

        lines = [f"=== ТРАНЗИТЫ СЕГОДНЯ ({dt_now.strftime('%d.%m.%Y')}) ==="]
        if transits_found:
            lines.extend(transits_found[:8])
        else:
            lines.append("  Значимых транзитов не обнаружено.")

        return "\n".join(lines)

    except Exception as e:
        return f"[Транзиты недоступны: {e}]"


def get_full_astro_context(
    birth_date: Optional[str] = None,
    birth_time: Optional[str] = None,
    birth_place: Optional[str] = None,
) -> str:
    """
    Полный астро-контекст для инъекции в промпт Claude.
    Если переданы данные рождения — добавляет натальную карту и транзиты.
    """
    parts = [get_current_sky()]

    if birth_date and birth_time and birth_place:
        parts.append("")
        parts.append(get_natal_chart(birth_date, birth_time, birth_place))
        parts.append("")
        parts.append(get_transit_context(birth_date, birth_time, birth_place))

    return "\n".join(parts)


if __name__ == "__main__":
    # Тест
    print(get_current_sky())
    print()
    print(get_natal_chart("27.09.1983", "23:30", "г. Находка, Приморский край"))
    print()
    print(get_transit_context("27.09.1983", "23:30", "г. Находка, Приморский край"))
