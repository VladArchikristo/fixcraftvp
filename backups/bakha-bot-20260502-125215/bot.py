#!/usr/bin/env python3
"""Bakhtiyar (Bakha) Telegram bot.

Clean-room implementation: created from scratch, not copied from other local bots.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Deque

from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

BOT_NAME = "Бахтияр"
SHORT_NAME = "Баха"
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = Path.home() / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
PID_FILE = LOG_DIR / "bakha-bot.pid"
LOG_FILE = LOG_DIR / "bakha-bot.log"

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:10531/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")
MAX_HISTORY_MESSAGES = 12
MAX_USER_TEXT_CHARS = 45000
REQUEST_TIMEOUT_SECONDS = 900

SYSTEM_PROMPT = """
Ты — Бахтияр, сокращённо Баха. Ты полностью новый Telegram-бот, созданный с нуля.
Ты не наследуешь личность, память, стиль, логи или внутренние правила других ботов.

Кто ты:
- Крутой IT-инженер и программист уровня senior/staff.
- Programmer-architect: умеешь проектировать системы, писать код, чинить баги, объяснять архитектуру.
- Практичный инженер: сначала понимаешь задачу, потом даёшь рабочее решение.
- Говоришь по-русски прямо, спокойно, без воды. Если нужен код — даёшь код.

Твои сильные стороны:
- Python, TypeScript, JavaScript, Node.js, Next.js, React, SQL, Bash.
- Telegram bots, API integrations, automation, backend, frontend, DevOps basics.
- Debugging: воспроизведение, гипотезы, проверка, минимальный фикс.
- Architecture: простая схема, границы ответственности, данные, отказоустойчивость.
- Code review: безопасность, edge cases, читаемость, стоимость поддержки.
- Git/GitHub workflow: ветки, PR, ревью, issues, CI/CD concepts.

Инженерные правила:
1. Не выдумывай факты. Если данных нет — скажи что нужно проверить.
2. Предпочитай простые решения сложным.
3. Не переписывай всё, если нужен маленький фикс.
4. Для багов: причина → проверка → фикс → как убедиться что работает.
5. Для новых проектов: минимальная рабочая версия → проверка → улучшения.
6. Безопасность: не проси и не показывай секреты в открытом виде.
7. Если пользователь зол или торопится — отвечай короче и по делу.

Как отвечать:
- Сначала вывод/решение, потом детали.
- Не начинай с длинных вступлений.
- Используй Markdown: списки и код-блоки.
- Если есть риск сломать production — прямо предупреди.
- Если вопрос простой — отвечай коротко.
""".strip()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("bakha-bot")

_histories: dict[int, Deque[dict[str, str]]] = defaultdict(lambda: deque(maxlen=MAX_HISTORY_MESSAGES))
_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(base_url=OPENAI_BASE_URL, api_key=os.getenv("OPENAI_API_KEY", "not-needed"))
    return _client


def build_messages(chat_id: int, user_text: str) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(_histories[chat_id])
    messages.append({"role": "user", "content": user_text[:MAX_USER_TEXT_CHARS]})
    return messages


def ask_gpt(messages: list[dict[str, str]]) -> str:
    response = get_client().chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0.25,
        max_tokens=4096,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if not response.choices:
        raise RuntimeError("GPT returned no choices")
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("GPT returned empty content")
    return content.strip()


def allowed_user_ids() -> set[int]:
    raw = os.getenv("ALLOWED_USER_ID", "244710532")
    ids: set[int] = set()
    for part in raw.replace(",", " ").split():
        try:
            ids.add(int(part))
        except ValueError:
            log.warning("Bad ALLOWED_USER_ID value: %r", part)
    return ids or {244710532}


def is_allowed(update: Update) -> bool:
    user = update.effective_user
    return bool(user and user.id in allowed_user_ids())


async def reject(update: Update) -> None:
    if update.message:
        await update.message.reply_text("Доступ закрыт.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await reject(update)
        return
    text = (
        "Я Бахтияр, можно Баха. Новый чистый бот-инженер.\n\n"
        "Могу помогать с кодом, архитектурой, багами, GitHub, API, ботами и DevOps.\n"
        "Команды: /status, /clear"
    )
    await update.message.reply_text(text)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await reject(update)
        return
    text = (
        f"{BOT_NAME} online.\n"
        f"Model: {OPENAI_MODEL}\n"
        f"Proxy: {OPENAI_BASE_URL}\n"
        f"PID: {os.getpid()}"
    )
    await update.message.reply_text(text)


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await reject(update)
        return
    chat_id = update.effective_chat.id
    _histories.pop(chat_id, None)
    await update.message.reply_text("История очищена.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        await reject(update)
        return
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    user_text = update.message.text.strip()
    if not user_text:
        return

    log.info("Message from %s: %s", update.effective_user.id, user_text[:300])
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    messages = build_messages(chat_id, user_text)
    try:
        answer = await asyncio.to_thread(ask_gpt, messages)
    except Exception as exc:
        log.exception("GPT call failed")
        await update.message.reply_text(f"Ошибка GPT-5.5/proxy: {exc}")
        return

    _histories[chat_id].append({"role": "user", "content": user_text[:MAX_USER_TEXT_CHARS]})
    _histories[chat_id].append({"role": "assistant", "content": answer})

    for chunk in split_telegram(answer):
        await update.message.reply_text(chunk)


def split_telegram(text: str, limit: int = 3900) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = text
    while len(current) > limit:
        cut = current.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        chunks.append(current[:cut].strip())
        current = current[cut:].strip()
    if current:
        chunks.append(current)
    return chunks


def write_pid() -> None:
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def remove_pid(*_args: object) -> None:
    try:
        if PID_FILE.exists() and PID_FILE.read_text(encoding="utf-8").strip() == str(os.getpid()):
            PID_FILE.unlink()
    except Exception:
        pass


def main() -> None:
    load_dotenv(BASE_DIR / ".env")
    token = os.getenv("BAKHA_BOT_TOKEN")
    if not token:
        raise SystemExit("BAKHA_BOT_TOKEN is missing in .env")

    write_pid()
    signal.signal(signal.SIGTERM, remove_pid)
    signal.signal(signal.SIGINT, remove_pid)

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    log.info("%s starting, PID %s", BOT_NAME, os.getpid())
    try:
        app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
    finally:
        remove_pid()
        log.info("%s stopped", BOT_NAME)


if __name__ == "__main__":
    main()
