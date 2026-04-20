#!/usr/bin/env python3
"""
Автоматическое извлечение ключевых фактов из сообщений пользователя.
Лёгкий модуль — regex-паттерны, без вызовов AI.

v2: расширенные паттерны (RU + EN), лучшее покрытие,
    извлечение из ответов бота, нормализация фактов.
"""

import re
from shared_memory import save_fact

# ===================== ПАТТЕРНЫ ПОЛЬЗОВАТЕЛЯ =====================

# Формат: (regex, category, template)
# template: None = используем match group, str = форматируем с match groups
PATTERNS_RU = [
    # Предпочтения
    (r"(?:я\s+)?(?:предпочитаю|люблю|обожаю|выбираю)\s+(.{5,80})", "preference", None),
    (r"(?:мне\s+)?(?:нравится|подходит|удобно)\s+(.{5,80})", "preference", None),
    (r"(?:я\s+)?(?:использую|юзаю|пользуюсь)\s+(.{5,80})", "preference", "использует: {0}"),
    # Личное
    (r"(?:мой|моя|моё|мои)\s+(\w+)\s+(?:—|это|[-–:])\s*(.{3,60})", "personal", "{0}: {1}"),
    (r"я\s+(?:живу|нахожусь)\s+(?:в|на)\s+(.{3,60})", "personal", "локация: {0}"),
    (r"я\s+(?:работаю|тружусь)\s+(.{5,80})", "personal", "работа: {0}"),
    (r"я\s+(?:учусь|изучаю|занимаюсь)\s+(.{5,80})", "personal", "занятие: {0}"),
    (r"мне\s+(\d+)\s+(?:лет|год|года)", "personal", "возраст: {0}"),
    (r"меня\s+зовут\s+(\w+)", "personal", "имя: {0}"),
    # Проекты и задачи
    (r"(?:работаю\s+над|делаю|пилю|строю)\s+(.{5,80})", "project", None),
    (r"(?:проект|приложение|бот|сайт)\s+(.{5,80})", "project", None),
    (r"(?:запустил|создал|развернул|задеплоил)\s+(.{5,80})", "project", "запустил: {0}"),
    # Решения и планы
    (r"(?:решил|буду|планирую|собираюсь|хочу)\s+(.{5,80})", "decision", None),
    (r"(?:надо|нужно|пора)\s+(.{5,80})", "decision", "план: {0}"),
    # Дизлайки
    (r"(?:не\s+люблю|ненавижу|не\s+хочу|бесит|раздражает)\s+(.{5,80})", "dislike", None),
    # Финансы / трейдинг
    (r"(?:купил|продал|открыл|закрыл)\s+(.{5,80})", "trading", None),
    (r"(?:портфель|баланс|депозит|счёт)\s*[:—-]\s*(.{5,80})", "trading", None),
    (r"(?:бюджет|трачу|подписка|стоит)\s+(.{5,80})", "finance", None),
    # Здоровье (для Петра)
    (r"(?:болит|аллергия|принимаю|диагноз)\s+(.{5,80})", "health", None),
    # Технические
    (r"(?:токен|api.?key|пароль|ключ)\s+(?:для\s+)?(\w+)\s+(.{5,50})", "config", "config {0}: {1}"),
    (r"(?:версия|version)\s+(.{3,30})", "config", "версия: {0}"),
]

PATTERNS_EN = [
    (r"(?:I\s+)?(?:prefer|like|love|use)\s+(.{5,80})", "preference", None),
    (r"(?:I\s+)?(?:work|live|study)\s+(?:on|in|at)\s+(.{5,80})", "personal", None),
    (r"(?:I\s+)?(?:want|plan|need)\s+to\s+(.{5,80})", "decision", None),
    (r"(?:bought|sold|opened|closed)\s+(.{5,80})", "trading", None),
    (r"(?:budget|spend|cost|price)\s*[:—-]?\s*(.{5,80})", "finance", None),
    (r"(?:my\s+)(\w+)\s+(?:is|are|was)\s+(.{3,60})", "personal", "{0}: {1}"),
]

# Команды-подсказки (прямое "запомни")
REMEMBER_PATTERNS = [
    r"запомни[:\s]+(.{5,200})",
    r"помни[:\s]+(.{5,200})",
    r"важно[:\s]+(.{5,200})",
    r"не\s*забудь[:\s]+(.{5,200})",
    r"remember[:\s]+(.{5,200})",
    r"note[:\s]+(.{5,200})",
    r"save[:\s]+(.{5,200})",
]


def _normalize_fact(text: str) -> str:
    """Нормализует факт: убирает лишние пробелы, пунктуацию в конце."""
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    text = text.rstrip(".,;:!?…")
    # Ограничиваем длину
    if len(text) > 150:
        text = text[:147] + "…"
    return text


def _apply_template(template, groups):
    """Применяет шаблон к группам regex."""
    if template is None:
        return " ".join(g.strip() for g in groups if g)
    try:
        return template.format(*[g.strip() for g in groups if g])
    except (IndexError, KeyError):
        return " ".join(g.strip() for g in groups if g)


def extract_facts(user_id: int, bot_name: str, user_text: str) -> list[str]:
    """
    Извлекает факты из текста пользователя и сохраняет в БД.
    Возвращает список извлечённых фактов (для логирования).
    """
    if not user_text or len(user_text) < 5:
        return []

    extracted = []
    text = user_text.strip()
    text_lower = text.lower()

    # 1. Прямые команды "запомни" — приоритет
    for pattern in REMEMBER_PATTERNS:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            fact = _normalize_fact(match.group(1))
            if len(fact) >= 5:
                save_fact(user_id, bot_name, fact, "explicit")
                extracted.append(fact)

    # Если нашли явную команду — не ищем автоматически
    if extracted:
        return extracted[:3]

    # 2. Автоматические паттерны (RU)
    for pattern, category, template in PATTERNS_RU:
        matches = list(re.finditer(pattern, text_lower, re.IGNORECASE))
        for match in matches:
            groups = match.groups()
            raw = _apply_template(template, groups)
            fact = _normalize_fact(raw)
            if 5 <= len(fact) <= 200:
                save_fact(user_id, bot_name, fact, category)
                extracted.append(fact)
                break  # одного факта на паттерн

    # 3. Автоматические паттерны (EN)
    for pattern, category, template in PATTERNS_EN:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        for match in matches:
            groups = match.groups()
            raw = _apply_template(template, groups)
            fact = _normalize_fact(raw)
            if 5 <= len(fact) <= 200:
                save_fact(user_id, bot_name, fact, category)
                extracted.append(fact)
                break

    return extracted[:5]  # максимум 5 фактов за сообщение


def extract_facts_from_exchange(user_id: int, bot_name: str,
                                 user_text: str, bot_response: str) -> list[str]:
    """
    Извлекает факты из обмена сообщениями (user + bot response).
    Вызывается ПОСЛЕ каждого ответа бота.
    """
    facts = extract_facts(user_id, bot_name, user_text)

    # Из ответа бота — рекомендации, итоги, решения
    if bot_response and len(bot_response) > 20:
        response_lower = bot_response.lower()
        bot_patterns = [
            (r"рекомендую\s+(.{10,100})", "recommendation"),
            (r"итог[:\s]+(.{10,200})", "summary"),
            (r"вывод[:\s]+(.{10,200})", "summary"),
            (r"решение[:\s]+(.{10,200})", "decision"),
            (r"результат[:\s]+(.{10,200})", "summary"),
            (r"статус[:\s]+(.{10,100})", "status"),
            # Числовые результаты (портфель, прибыль)
            (r"(?:прибыль|убыток|доход|P&L)[:\s]*([+-]?\$?[\d,.]+%?)", "trading"),
            (r"(?:profit|loss|P&L)[:\s]*([+-]?\$?[\d,.]+%?)", "trading"),
        ]
        for pattern, category in bot_patterns:
            match = re.search(pattern, response_lower)
            if match:
                fact = _normalize_fact(match.group(1))
                if len(fact) >= 5:
                    save_fact(user_id, bot_name, f"[бот] {fact}", category)
                    facts.append(fact)
                    break

    return facts[:5]
