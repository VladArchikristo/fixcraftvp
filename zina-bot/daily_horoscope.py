#!/usr/bin/env python3
"""
Зина — ежедневный гороскоп и нумерологический паттерн.
Запускается каждый день в 8:00 по расписанию (cron).
Отправляет Владимиру персональный прогноз в Telegram.
"""

import os
import sys
import subprocess
import requests
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent

# Загружаем токен из .env вручную (без зависимостей)
env_file = SCRIPT_DIR / ".env"
env_vars = {}
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            env_vars[key.strip()] = val.strip()

BOT_TOKEN = env_vars.get("ZINA_BOT_TOKEN", "")
CHAT_ID = int(env_vars.get("ALLOWED_USER_ID", "244710532"))
CLAUDE_PATH = "/Users/vladimirprihodko/.local/bin/claude"
LOG_FILE = Path.home() / "logs" / "zina-daily.log"

# Данные Владимира
BIRTH_DATE = "27.09.1983"
BIRTH_TIME = "23:30"
BIRTH_PLACE = "г. Находка, Приморский край"
FULL_NAME = "Приходько Владимир Геннадьевич"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Генерация гороскопа через Claude CLI
# ---------------------------------------------------------------------------
def generate_horoscope(today: str) -> str:
    prompt = f"""Ты — Зина, мудрый астро-нумерологический наставник.

Данные пользователя:
- Имя: {FULL_NAME}
- Дата рождения: {BIRTH_DATE}
- Время рождения: {BIRTH_TIME}
- Место рождения: {BIRTH_PLACE}
- Сегодня: {today}

Составь персональный прогноз на сегодня ({today}). Включи:

1. **Нумерологический паттерн дня** — рассчитай личный день (с формулой), объясни его энергию
2. **Астрологический акцент** — ключевой транзит или аспект дня, как он влияет лично на Владимира
3. **Главная задача дня** — одно ключевое действие, которое карта поддерживает сегодня
4. **Чего остеречься** — одно предупреждение
5. **Слово дня** — одно слово или короткая фраза-мантра

Пиши конкретно, глубоко, без банальностей. Максимум 350 слов. Форматируй с заголовками Markdown."""

    try:
        result = subprocess.run(
            [CLAUDE_PATH, "--model", "claude-haiku-4-5", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(SCRIPT_DIR),
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        else:
            log(f"Claude error: {result.stderr[:200]}")
            return None
    except subprocess.TimeoutExpired:
        log("Claude timeout при генерации гороскопа")
        return None
    except Exception as e:
        log(f"Ошибка запуска Claude: {e}")
        return None


# ---------------------------------------------------------------------------
# Отправка в Telegram
# ---------------------------------------------------------------------------
def sanitize_markdown(text: str) -> str:
    """Фиксит сломанный Markdown от Claude — закрывает незакрытые сущности.

    Более надёжная версия: обрабатывает [] ссылки, вложенный markdown,
    escape-символы MarkdownV2, и edge cases с byte offset ошибками.
    """
    import re

    # 1. Убираем MarkdownV2 escape-символы (\* \_ \[ \] и т.д.)
    #    Telegram Markdown v1 их НЕ понимает — они вызывают parse error
    text = re.sub(r'\\([*_`\[\]()~>#+\-=|{}.!])', r'\1', text)

    # 2. Защищаем ``` блоки — заменяем спец-символы внутри
    text = re.sub(r'```[\s\S]*?```', lambda m: m.group(0).replace('*', '✱').replace('_', '⎽'), text)

    # 3. Убираем тройные *** (bold+italic) — Telegram v1 не поддерживает
    text = text.replace('***', '**')

    # 4. Фиксим незакрытые [] ссылки — частая причина byte offset ошибок
    #    Убираем [text](url) формат — Telegram Markdown v1 не поддерживает inline links
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)
    #    Одинокие [ или ] — убираем
    bracket_open = text.count('[')
    bracket_close = text.count(']')
    if bracket_open != bracket_close:
        text = text.replace('[', '').replace(']', '')

    # 5. Проверяем парность * _ `
    # ** (bold)
    double_count = text.count('**')
    if double_count % 2 != 0:
        idx = text.rfind('**')
        text = text[:idx] + text[idx+2:]

    # Одинарные * (italic) — считаем без **
    temp = text.replace('**', '')
    if temp.count('*') % 2 != 0:
        # Ищем последний одинарный * (не часть **)
        for i in range(len(text) - 1, -1, -1):
            if text[i] == '*':
                # Не часть **
                is_double = (i > 0 and text[i-1] == '*') or (i < len(text)-1 and text[i+1] == '*')
                if not is_double:
                    text = text[:i] + text[i+1:]
                    break

    # _ (italic)
    if text.count('_') % 2 != 0:
        idx = text.rfind('_')
        text = text[:idx] + text[idx+1:]

    # ``` (code blocks)
    triple = text.count('```')
    if triple % 2 != 0:
        idx = text.rfind('```')
        text = text[:idx] + text[idx+3:]

    # ` (inline code) — считаем без ```
    temp = text.replace('```', '')
    if temp.count('`') % 2 != 0:
        idx = text.rfind('`')
        text = text[:idx] + text[idx+1:]

    return text


def send_telegram(text: str) -> bool:
    if not BOT_TOKEN:
        log("BOT_TOKEN не найден!")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    # Санитизируем Markdown перед отправкой
    text = sanitize_markdown(text)

    # Telegram лимит — 4096 символов. Режем если надо.
    chunks = []
    while len(text) > 4000:
        split_at = text.rfind("\n", 0, 4000)
        if split_at == -1:
            split_at = 4000
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()
    chunks.append(text)

    for i, chunk in enumerate(chunks):
        try:
            resp = requests.post(url, json={
                "chat_id": CHAT_ID,
                "text": chunk,
                "parse_mode": "Markdown",
            }, timeout=30)
            if not resp.ok:
                log(f"Telegram Markdown error [{i+1}]: {resp.text[:200]}")
                # Пробуем без Markdown — гарантированная доставка
                resp2 = requests.post(url, json={
                    "chat_id": CHAT_ID,
                    "text": chunk,
                }, timeout=30)
                if not resp2.ok:
                    log(f"Telegram plain error [{i+1}]: {resp2.text[:200]}")
                    return False
                log(f"Chunk [{i+1}] доставлен без форматирования")
        except Exception as e:
            log(f"Ошибка отправки в Telegram: {e}")
            return False

    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    today = datetime.now().strftime("%d.%m.%Y")
    weekday_ru = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    weekday = weekday_ru[datetime.now().weekday()]

    log(f"Генерация ежедневного гороскопа на {today} ({weekday})...")

    # Заголовок сообщения
    header = f"🌙 *Зина • {today} • {weekday.capitalize()}*\n\n"

    horoscope = generate_horoscope(f"{today}, {weekday}")

    if not horoscope:
        log("Не удалось сгенерировать гороскоп")
        # Отправляем сообщение об ошибке
        send_telegram(f"⚠️ Зина не смогла составить прогноз на {today}. Попробуй запросить вручную.")
        sys.exit(1)

    full_message = header + horoscope

    if send_telegram(full_message):
        log(f"Гороскоп на {today} успешно отправлен")
    else:
        log("Ошибка отправки в Telegram")
        sys.exit(1)


if __name__ == "__main__":
    main()
