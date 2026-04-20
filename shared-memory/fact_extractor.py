#!/usr/bin/env python3
"""
Автоматическое извлечение ключевых фактов из сообщений.

v3: Haiku AI extraction (основной) + regex fallback.
    Haiku через Claude CLI — не нужен API ключ.
    Фоновое извлечение — не блокирует ответ бота.
"""

import re
import os
import json
import subprocess
import threading
import logging
from shared_memory import save_fact

log = logging.getLogger("fact_extractor")

# Claude CLI path — ищем во всех возможных местах
CLAUDE_PATH = None
_candidates = [
    os.path.expanduser("~/.local/bin/claude"),  # основной путь на Mac Mini
    "/usr/local/bin/claude",
    "/opt/homebrew/bin/claude",
    os.path.expanduser("~/.claude/local/claude"),
]
for _p in _candidates:
    if os.path.exists(_p):
        CLAUDE_PATH = _p
        break
if CLAUDE_PATH is None:
    # fallback — попробуем через which
    import shutil
    CLAUDE_PATH = shutil.which("claude") or "claude"

HAIKU_MODEL = "haiku"
HAIKU_TIMEOUT = 60  # секунд — Claude CLI ~35 сек cold start + Haiku ответ

# Минимальная длина сообщения для вызова Haiku (экономия)
MIN_TEXT_FOR_HAIKU = 15
# Минимальная длина ответа бота для анализа
MIN_RESPONSE_FOR_HAIKU = 30

# ===================== HAIKU EXTRACTION =====================

EXTRACTION_SYSTEM = (
    "Извлеки ключевые факты о пользователе из диалога. "
    "Только КОНКРЕТНЫЕ: имя, локация, проект, предпочтение, решение, число, дата. "
    "НЕ извлекай команды, вопросы, приветствия. "
    'Категории: personal, preference, project, decision, trading, finance, health, config, status. '
    'Ответ: JSON массив [{"fact":"...","category":"..."}]. Макс 3 факта. Если нет — []. '
    "Факт до 100 символов."
)


def _call_haiku(user_text: str, bot_response: str) -> list[dict]:
    """Вызывает Haiku через CLI для извлечения фактов. Возвращает [{fact, category}]."""
    # Инструкция + данные в одном промте (через stdin)
    prompt = (
        f"{EXTRACTION_SYSTEM}\n\n"
        f"User: {user_text[:500]}\n"
        f"Bot: {bot_response[:500] if bot_response else '(нет)'}"
    )

    try:
        proc = subprocess.run(
            [CLAUDE_PATH, "-p", "--model", HAIKU_MODEL, "--output-format", "text",
             "--max-turns", "1"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=HAIKU_TIMEOUT,
        )
        if proc.returncode != 0:
            log.debug("Haiku exited %d", proc.returncode)
            return []

        raw = proc.stdout.strip()
        # Извлекаем JSON из ответа
        # Haiku может обернуть в ```json ... ``` или вернуть просто массив
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        raw = raw.strip()

        if not raw or raw == "[]":
            return []

        facts = json.loads(raw)
        if not isinstance(facts, list):
            return []

        # Валидация
        result = []
        for f in facts[:3]:
            if isinstance(f, dict) and "fact" in f:
                fact_text = str(f["fact"]).strip()
                category = str(f.get("category", "general")).strip()
                if 5 <= len(fact_text) <= 150:
                    result.append({"fact": fact_text, "category": category})
        return result

    except subprocess.TimeoutExpired:
        log.debug("Haiku timed out")
        return []
    except (json.JSONDecodeError, Exception) as e:
        log.debug("Haiku parse error: %s", e)
        return []


# ===================== REGEX FALLBACK =====================

PATTERNS_RU = [
    (r"(?:я\s+)?(?:предпочитаю|люблю|обожаю|выбираю)\s+(.{5,80})", "preference", None),
    (r"(?:мне\s+)?(?:нравится|подходит|удобно)\s+(.{5,80})", "preference", None),
    (r"(?:я\s+)?(?:использую|юзаю|пользуюсь)\s+(.{5,80})", "preference", "использует: {0}"),
    (r"(?:мой|моя|моё|мои)\s+(\w+)\s+(?:—|это|[-–:])\s*(.{3,60})", "personal", "{0}: {1}"),
    (r"я\s+(?:живу|нахожусь)\s+(?:в|на)\s+(.{3,60})", "personal", "локация: {0}"),
    (r"я\s+(?:работаю|тружусь)\s+(.{5,80})", "personal", "работа: {0}"),
    (r"мне\s+(\d+)\s+(?:лет|год|года)", "personal", "возраст: {0}"),
    (r"меня\s+зовут\s+(\w+)", "personal", "имя: {0}"),
    (r"(?:работаю\s+над|делаю|пилю|строю)\s+(.{5,80})", "project", None),
    (r"(?:запустил|создал|развернул|задеплоил)\s+(.{5,80})", "project", "запустил: {0}"),
    (r"(?:решил|буду|планирую|собираюсь)\s+(.{5,80})", "decision", None),
    (r"(?:купил|продал|открыл|закрыл)\s+(.{5,80})", "trading", None),
    (r"(?:болит|аллергия|принимаю|диагноз)\s+(.{5,80})", "health", None),
]

REMEMBER_PATTERNS = [
    r"запомни[:\s]+(.{5,200})",
    r"помни[:\s]+(.{5,200})",
    r"важно[:\s]+(.{5,200})",
    r"не\s*забудь[:\s]+(.{5,200})",
    r"remember[:\s]+(.{5,200})",
]


def _normalize_fact(text: str) -> str:
    """Нормализует факт: убирает лишние пробелы, пунктуацию."""
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    text = text.rstrip(".,;:!?…")
    if len(text) > 150:
        text = text[:147] + "…"
    return text


def _apply_template(template, groups):
    if template is None:
        return " ".join(g.strip() for g in groups if g)
    try:
        return template.format(*[g.strip() for g in groups if g])
    except (IndexError, KeyError):
        return " ".join(g.strip() for g in groups if g)


def _regex_extract(user_text: str) -> list[tuple[str, str]]:
    """Regex fallback — возвращает [(fact, category)]."""
    if not user_text or len(user_text) < 5:
        return []

    results = []
    text_lower = user_text.strip().lower()

    # Прямые команды "запомни"
    for pattern in REMEMBER_PATTERNS:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            fact = _normalize_fact(match.group(1))
            if len(fact) >= 5:
                results.append((fact, "explicit"))
    if results:
        return results[:3]

    # Авто-паттерны
    for pattern, category, template in PATTERNS_RU:
        matches = list(re.finditer(pattern, text_lower, re.IGNORECASE))
        for match in matches:
            raw = _apply_template(template, match.groups())
            fact = _normalize_fact(raw)
            if 5 <= len(fact) <= 200:
                results.append((fact, category))
                break
    return results[:5]


# ===================== MAIN API =====================

def extract_facts(user_id: int, bot_name: str, user_text: str) -> list[str]:
    """
    Извлекает факты из текста пользователя (regex only, синхронно).
    Сохраняет в БД. Возвращает список фактов.
    """
    extracted = []
    for fact, category in _regex_extract(user_text):
        save_fact(user_id, bot_name, fact, category)
        extracted.append(fact)
    return extracted


def extract_facts_from_exchange(user_id: int, bot_name: str,
                                 user_text: str, bot_response: str) -> list[str]:
    """
    Извлекает факты из обмена (user + bot response).
    Использует Haiku в фоне + regex как быстрый fallback.
    Вызывается ПОСЛЕ каждого ответа бота.
    """
    # 1. Regex — мгновенно, синхронно (для прямых команд "запомни")
    quick_facts = []
    for fact, category in _regex_extract(user_text):
        save_fact(user_id, bot_name, fact, category)
        quick_facts.append(fact)

    # 2. Haiku — в фоновом потоке (не блокирует)
    user_len = len(user_text) if user_text else 0
    resp_len = len(bot_response) if bot_response else 0

    if user_len >= MIN_TEXT_FOR_HAIKU or resp_len >= MIN_RESPONSE_FOR_HAIKU:
        thread = threading.Thread(
            target=_haiku_extract_background,
            args=(user_id, bot_name, user_text or "", bot_response or ""),
            daemon=True,
        )
        thread.start()

    return quick_facts


def _haiku_extract_background(user_id: int, bot_name: str,
                               user_text: str, bot_response: str):
    """Фоновое извлечение фактов через Haiku."""
    try:
        facts = _call_haiku(user_text, bot_response)
        for f in facts:
            save_fact(user_id, bot_name, f["fact"], f["category"], source="haiku")
            log.info("[%s] Haiku fact: [%s] %s", bot_name, f["category"], f["fact"])
    except Exception as e:
        log.debug("Haiku background error: %s", e)
