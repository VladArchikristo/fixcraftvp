#!/usr/bin/env python3
"""
Автоматическое извлечение ключевых фактов из сообщений пользователя.
Лёгкий модуль — regex-паттерны, без вызовов AI.
~300 токенов экономии на каждый факт vs полное сообщение.
"""

import re
from shared_memory import save_fact

# Паттерны для извлечения фактов
PATTERNS = [
    # Предпочтения: "я предпочитаю X", "мне нравится X", "люблю X"
    (r"(?:я\s+)?(?:предпочитаю|люблю|обожаю|хочу)\s+(.{5,80})", "preference"),
    # Мой X: "мой телефон iPhone", "моя машина Tesla"
    (r"(?:мой|моя|моё|мои)\s+(\w+)\s+(?:—|это|[-–])\s*(.{3,60})", "personal"),
    # Факты о себе: "я живу в", "я работаю", "мне X лет"
    (r"я\s+(?:живу|работаю|учусь|занимаюсь)\s+(.{5,80})", "personal"),
    (r"мне\s+(\d+)\s+(?:лет|год|года)", "personal"),
    # Проекты: "проект X", "работаю над X"
    (r"(?:работаю\s+над|проект|делаю)\s+(.{5,80})", "project"),
    # Важные решения: "решил X", "буду X", "планирую X"
    (r"(?:решил|буду|планирую|собираюсь)\s+(.{5,80})", "decision"),
    # Не нравится: "не люблю X", "ненавижу X", "не хочу X"
    (r"(?:не\s+люблю|ненавижу|не\s+хочу|бесит)\s+(.{5,80})", "dislike"),
    # Имена: "меня зовут X", "я X"
    (r"меня\s+зовут\s+(\w+)", "personal"),
    # Часовой пояс, локация
    (r"(?:я\s+(?:в|из)\s+)(\w+(?:\s+\w+)?)", "location"),
]

# Команды-подсказки (если пользователь прямо говорит "запомни")
REMEMBER_PATTERNS = [
    r"запомни[:\s]+(.{5,200})",
    r"помни[:\s]+(.{5,200})",
    r"важно[:\s]+(.{5,200})",
    r"не забудь[:\s]+(.{5,200})",
]


def extract_facts(user_id: int, bot_name: str, user_text: str) -> list[str]:
    """
    Извлекает факты из текста пользователя и сохраняет в БД.
    Возвращает список извлечённых фактов (для логирования).
    """
    if not user_text or len(user_text) < 5:
        return []

    extracted = []
    text_lower = user_text.lower().strip()

    # Прямые команды "запомни"
    for pattern in REMEMBER_PATTERNS:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            fact = match.group(1).strip().rstrip(".")
            if len(fact) >= 5:
                save_fact(user_id, bot_name, fact, "explicit")
                extracted.append(fact)

    # Автоматические паттерны (только если нет прямой команды)
    if not extracted:
        for pattern, category in PATTERNS:
            matches = re.finditer(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                groups = match.groups()
                fact = " ".join(g.strip() for g in groups if g).rstrip(".")
                if len(fact) >= 5 and len(fact) <= 200:
                    save_fact(user_id, bot_name, fact, category)
                    extracted.append(fact)
                    break  # одного факта на паттерн достаточно

    return extracted[:3]  # максимум 3 факта за сообщение


def extract_facts_from_exchange(user_id: int, bot_name: str,
                                 user_text: str, bot_response: str) -> list[str]:
    """
    Извлекает факты из обмена сообщениями (и user, и bot response).
    Вызывается ПОСЛЕ каждого ответа бота.
    """
    facts = extract_facts(user_id, bot_name, user_text)

    # Из ответа бота извлекаем только "решения" и "рекомендации"
    if bot_response and len(bot_response) > 20:
        response_lower = bot_response.lower()
        # Если бот дал конкретную рекомендацию
        rec_patterns = [
            (r"рекомендую\s+(.{10,100})", "recommendation"),
            (r"итог[:\s]+(.{10,200})", "summary"),
            (r"вывод[:\s]+(.{10,200})", "summary"),
        ]
        for pattern, category in rec_patterns:
            match = re.search(pattern, response_lower)
            if match:
                fact = match.group(1).strip().rstrip(".")
                if len(fact) >= 10:
                    save_fact(user_id, bot_name, f"[бот] {fact}", category)
                    facts.append(fact)
                    break

    return facts[:3]
