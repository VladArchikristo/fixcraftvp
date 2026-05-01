#!/usr/bin/env python3
"""
Костя — бот-программист архитектор.
GPT-5.5 | Читает фото | Знает всех ботов | Создаёт суббота.
Singleton, LaunchAgent restarts, heartbeat, OpenAI SDK via proxy.
"""
from __future__ import annotations

import atexit
import os
import sys
import fcntl
import signal
import time
import logging
from logging.handlers import RotatingFileHandler
import subprocess
import asyncio
import threading
from pathlib import Path

# Суб-агенты — параллельное выполнение маленьких задач
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.subagent_utils import two_pass_call, _get_claude_env
from datetime import datetime

# Shared memory
sys.path.insert(0, '/Users/vladimirprihodko/Папка тест/fixcraftvp/shared-memory')
from shared_memory import save_message, get_history as sm_get_history, clear_history as sm_clear_history, save_fact, get_facts, build_memory_prompt, save_session_summary
from fact_extractor import extract_facts_from_exchange
from collections import deque
from concurrent.futures import ThreadPoolExecutor

import json
import tempfile
from dotenv import load_dotenv
from telegram import Update
from telegram.error import Conflict, NetworkError, TimedOut
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")

BOT_TOKEN = os.getenv("KOSTYA_BOT_TOKEN", "")
ALLOWED_USER = 244710532
CLAUDE_PATH = "/Users/vladimirprihodko/.local/bin/claude"
PROJECT_ROOT = Path("/Users/vladimirprihodko/Папка тест/fixcraftvp")
WORKING_DIR = str(PROJECT_ROOT)
CLAUDE_TIMEOUT = 600          # Текст — макс 10 мин
CLAUDE_PHOTO_TIMEOUT = 60     # Фото — макс 1 минута
PROCESSING_HARD_RESET = 660   # Аварийный сброс _processing через 11 мин
RATE_LIMIT_SEC = 3
MAX_PROMPT_CHARS = 60000

LOG_DIR = Path.home() / "logs"
LOG_DIR.mkdir(exist_ok=True)
PID_FILE = LOG_DIR / "kostya-bot.pid"
HEARTBEAT_FILE = LOG_DIR / "kostya-heartbeat"
LOCK_FILE = LOG_DIR / "kostya-bot.lock"

PHOTO_DIR = SCRIPT_DIR / "data" / "photos"
PHOTO_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Реестр ботов — добавляй сюда новых, Костя будет о них знать
# ---------------------------------------------------------------------------
BOTS_REGISTRY = {
    "vasily": {
        "label": "Василий",
        "handle": "@vasily_trader_bot",
        "role": "трейдер, финансовый аналитик",
        "dir": str(PROJECT_ROOT / "trading-bot"),
        "main_file": "telegram_bot.py",
        "pid_file": str(LOG_DIR / "vasily-bot.pid"),
        "log_file": str(LOG_DIR / "vasily-bot-main.log"),
        "heartbeat": str(LOG_DIR / "vasily-heartbeat"),
        "launcher": str(Path.home() / "vasily-launcher.sh"),
        "launchagent": "com.vasily.market-scan",
        "notes": "Основной файл: telegram_bot.py, логика сканов: market_scan.py, портфель: data/paper_portfolio.json",
    },
    "masha": {
        "label": "Маша",
        "handle": "@masha_marketer_bot",
        "role": "маркетолог, контент-менеджер",
        "dir": str(PROJECT_ROOT / "masha-bot"),
        "main_file": "bot.py",
        "pid_file": str(LOG_DIR / "masha-bot.pid"),
        "log_file": str(LOG_DIR / "masha-bot.log"),
        "heartbeat": str(LOG_DIR / "masha-heartbeat"),
        "launcher": str(Path.home() / "masha-launcher.sh"),
        "launchagent": "com.vladimir.masha-bot",
        "notes": "",
    },
    "beast": {
        "label": "Beast",
        "handle": "@Antropic_BeastBot",
        "role": "главный ассистент, точка входа от Влада",
        "dir": str(PROJECT_ROOT / "beast-bot"),
        "main_file": "bot.py",
        "pid_file": str(LOG_DIR / "beast-bot.pid"),
        "log_file": str(LOG_DIR / "beast-bot-main.log"),
        "heartbeat": str(LOG_DIR / "beast-heartbeat"),
        "launcher": str(Path.home() / "beast-launcher.sh"),
        "launchagent": "com.vladimir.beast-bot",
        "notes": "ВАЖНО: beast-bot/bot.py — НЕ редактировать никогда",
    },
    "kostya": {
        "label": "Костя",
        "handle": "@KostyaCoderBot",
        "role": "программист-архитектор, помогает всем ботам",
        "dir": str(PROJECT_ROOT / "coder-bot"),
        "main_file": "telegram_bot.py",
        "pid_file": str(LOG_DIR / "kostya-bot.pid"),
        "log_file": str(LOG_DIR / "kostya-bot-main.log"),
        "heartbeat": str(LOG_DIR / "kostya-heartbeat"),
        "launcher": str(Path.home() / "kostya-launcher.sh"),
        "launchagent": "com.vladimir.kostya-bot",
        "notes": "",
    },
    "philip": {
        "label": "Мыслитель Филип",
        "handle": "@PhilipThinkerBot",
        "role": "промт-инженер, полиглот, улучшает и создаёт промты",
        "dir": str(PROJECT_ROOT / "philip-bot"),
        "main_file": "bot.py",
        "pid_file": str(LOG_DIR / "philip-bot.pid"),
        "log_file": str(LOG_DIR / "philip-bot.log"),
        "heartbeat": str(LOG_DIR / "philip-heartbeat"),
        "launcher": str(Path.home() / "philip-launcher.sh"),
        "launchagent": "com.vladimir.philip-bot",
        "notes": "ask-philip.sh — делегировать промт-задачи Филипу",
    },
    "peter": {
        "label": "Пётр",
        "handle": "@PeterMedBot",
        "role": "медицинский ассистент, память здоровья",
        "dir": str(PROJECT_ROOT / "peter-bot"),
        "main_file": "telegram_bot.py",
        "pid_file": str(LOG_DIR / "peter-bot.pid"),
        "log_file": str(LOG_DIR / "peter-bot.log"),
        "heartbeat": str(LOG_DIR / "peter-heartbeat"),
        "launcher": str(Path.home() / "peter-launcher.sh"),
        "launchagent": "com.vladimir.peter-bot",
        "notes": "SQLite medical_memory, /memory /remember. Вызов: echo 'вопрос' | bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-peter.sh'",
    },
    "zina": {
        "label": "Зина",
        "handle": "@ZinaAstroBot",
        "role": "астролог, нумеролог, гороскопы",
        "dir": str(PROJECT_ROOT / "zina-bot"),
        "main_file": "telegram_bot.py",
        "pid_file": str(LOG_DIR / "zina-bot.pid"),
        "log_file": str(LOG_DIR / "zina-bot.log"),
        "heartbeat": str(LOG_DIR / "zina-heartbeat"),
        "launcher": str(Path.home() / "zina-launcher.sh"),
        "launchagent": "com.vladimir.zina-bot",
        "notes": "sonnet-4-6, астро/нумерология, только Влад. Вызов: echo 'вопрос' | bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-zina.sh'",
    },
}

# ---------------------------------------------------------------------------
# Шаблон нового бота (используется командой /newbot)
# ---------------------------------------------------------------------------
from bot_template import BOT_TEMPLATE


# ---------------------------------------------------------------------------
# System prompt — мега-программист с полным контекстом
# ---------------------------------------------------------------------------
def _build_bots_context() -> str:
    """Компактный список ботов для system prompt."""
    parts = [f"{b['label']} ({b['handle']}) — {b['role']}" for b in BOTS_REGISTRY.values()]
    return " | ".join(parts)


SYSTEM_PROMPT = f"""Ты — Костя, программист-архитектор. Правая рука Владимира на Mac Mini.

== СКИЛЛЫ ==
Python, JS/TS, Bash, SQL — senior. Архитектура, Telegram-боты, CLI, рефакторинг, аудит, отладка. Читаешь скриншоты и фото кода.

== МОДЕЛЬ ==
Ты используешь GPT-5.5 через локальный прокси (localhost:10531). НЕ называй себя Claude — ты на GPT.

== БОТЫ ЭКОСИСТЕМЫ ==
{_build_bots_context()}

НЕ ТРОГАТЬ НИКОГДА: beast-bot/bot.py, .env файлы, launcher.sh скрипты.

== ДЕЛЕГИРОВАНИЕ ==
Маша — маркетинг/контент | Василий — трейдинг/финансы | Филип — промты/архитектура.
Скрипты: bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-masha.sh' "задача"
(аналогично ask-vasily.sh, ask-philip.sh, ask-peter.sh, ask-zina.sh)

== СТИЛЬ ==
Русский, кратко, честно. Объясняй что делаешь.

== СУБ-АГЕНТЫ (Haiku, ~5 сек, параллельно) ==
Делегируй маленькие задачи тегами прямо в ответе:
<subagent type="research">вопрос</subagent>
<subagent type="code">что написать</subagent>
<subagent type="analyze">что проанализировать</subagent>
<subagent type="write">что написать</subagent>
<subagent type="quick">быстрый вопрос</subagent>
<subagent type="math">посчитать</subagent>
Несколько тегов = параллельный запуск. Не делегируй если нужен контекст диалога.
"""

START_TIME = datetime.now()
_claude_executor = ThreadPoolExecutor(max_workers=1)
_executor_lock = threading.Lock()  # защита от race condition при пересоздании executor
_processing = False
_processing_started: float = 0.0  # monotonic time когда началась обработка
_processing_lock = asyncio.Lock()
_last_message_time: float = 0.0
_rate_limit_lock = asyncio.Lock()
_current_proc: "subprocess.Popen | None" = None
_current_proc_lock = threading.Lock()


# _get_claude_env() импортирован из shared.subagent_utils (единая версия)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
_log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
_file_handler = RotatingFileHandler(
    LOG_DIR / "kostya-bot-main.log", maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_file_handler.setFormatter(_log_formatter)
# Только file handler — LaunchAgent redirects stdout to the same file, causing duplicates
logging.basicConfig(level=logging.INFO, handlers=[_file_handler])
log = logging.getLogger("kostya")

# Подавляем httpx/telegram логгеры — они сливают BOT_TOKEN в логи
for _noisy in ("httpx", "httpcore", "telegram.ext", "telegram.bot"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Singleton lock
# ---------------------------------------------------------------------------
_lock_fd = None


def acquire_lock():
    global _lock_fd
    _lock_fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        _lock_fd.close()
        _lock_fd = None
        log.info("Another instance is already running. Exiting.")
        sys.exit(0)
    _lock_fd.write(str(os.getpid()))
    _lock_fd.flush()


def write_pid():
    PID_FILE.write_text(str(os.getpid()))
    log.info("PID %d written to %s", os.getpid(), PID_FILE)


def write_heartbeat():
    HEARTBEAT_FILE.write_text(datetime.now().isoformat())


async def heartbeat_job(context: ContextTypes.DEFAULT_TYPE):
    global _processing, _claude_executor
    try:
        write_heartbeat()
    except Exception as e:
        log.error("Heartbeat write failed: %s", e)
    # Очистка старых фото (>7 дней)
    try:
        for f in Path(PHOTO_DIR).glob("photo_*.jpg"):
            if (time.time() - f.stat().st_mtime) > 7 * 86400:
                f.unlink(missing_ok=True)
                log.info("Deleted old photo: %s", f.name)
    except Exception as e:
        log.warning("Photo cleanup error: %s", e)
    # WATCHDOG: аварийный сброс _processing если зависло дольше PROCESSING_HARD_RESET
    if _processing and _processing_started > 0:
        stuck_sec = time.monotonic() - _processing_started
        if stuck_sec > PROCESSING_HARD_RESET:
            log.error("WATCHDOG: _processing stuck for %d sec — force reset!", int(stuck_sec))
            _kill_current_proc()
            old_executor = _claude_executor
            _claude_executor = ThreadPoolExecutor(max_workers=1)
            try:
                old_executor.shutdown(wait=False)
            except Exception:
                pass
            async with _processing_lock:
                _processing = False


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------
HISTORY_FILE = SCRIPT_DIR / "history.json"
user_history: deque = deque(maxlen=20)
CONVERSATION_LOG = SCRIPT_DIR / "conversation_log.jsonl"


def _log_conversation(role: str, text: str, user_id=None):
    entry = {
        "ts": datetime.now().isoformat(),
        "role": role,
        "user_id": user_id,
        "text": text[:5000],
    }
    try:
        # Ротация при >5MB
        log_path = Path(CONVERSATION_LOG)
        if log_path.exists() and log_path.stat().st_size > 5 * 1024 * 1024:
            rotated = Path(str(CONVERSATION_LOG) + ".1.jsonl")
            if rotated.exists():
                rotated.unlink(missing_ok=True)
            log_path.rename(rotated)
            log.info("Rotated conversation log (was >5MB)")
        with open(CONVERSATION_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        log.warning("Failed to write conversation log: %s", e)


def _load_history():
    if not HISTORY_FILE.exists():
        return
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("history is not a list")
        for item in data[-20:]:
            if isinstance(item, dict) and "role" in item and "text" in item:
                user_history.append(item)
        log.info("Loaded %d history messages", len(user_history))
    except (json.JSONDecodeError, ValueError) as e:
        log.error("History corrupted: %s. Starting fresh.", e)
        try:
            HISTORY_FILE.rename(HISTORY_FILE.with_suffix(".json.bak"))
        except Exception:
            pass
    except Exception as e:
        log.warning("Failed to load history: %s", e)


def _save_history():
    tmp_path = None
    try:
        data = json.dumps(list(user_history), ensure_ascii=False)
        fd, tmp_path = tempfile.mkstemp(dir=SCRIPT_DIR, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp_path, str(HISTORY_FILE))
        tmp_path = None
    except Exception as e:
        log.warning("Failed to save history: %s", e)
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def history_prompt(user_id: int | None = None) -> str:
    parts = []
    # Level 2+3: долгосрочная память (факты + сессии)
    if user_id is not None:
        mem = build_memory_prompt(user_id, "kostya")
        if mem:
            parts.append(mem)
    # Level 1: последние сообщения из SQLite shared memory
    if user_id is not None:
        try:
            msgs = sm_get_history(user_id, "kostya", limit=20)
            if msgs:
                parts.append("\n=== ПОСЛЕДНИЙ ДИАЛОГ ===")
                total_chars = 0
                for msg in msgs:
                    try:
                        role = "Влад" if msg.get("role") == "user" else "Костя"
                        content = msg.get("content") or msg.get("text") or ""
                        line = f"{role}: {content[:1000]}"
                        total_chars += len(line)
                        if total_chars > 8000:
                            break
                        parts.append(line)
                    except Exception as e:
                        log.warning("History message parse error: %s", e)
                        continue
                return "\n".join(parts)
        except Exception as e:
            log.error("Failed to load shared memory history: %s", e)
    # Fallback на in-memory deque
    if not user_history:
        return "\n".join(parts) if parts else ""
    total_chars = 0
    lines = []
    for msg in reversed(list(user_history)):
        role = "Влад" if msg["role"] == "user" else "Костя"
        line = f"{role}: {msg['text'][:1000]}"
        total_chars += len(line)
        if total_chars > 8000:
            break
        lines.append(line)
    lines.reverse()
    if lines:
        parts.append("\n=== ПОСЛЕДНИЙ ДИАЛОГ ===")
        parts.extend(lines)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Message split
# ---------------------------------------------------------------------------
def _split_message(text: str, limit: int = 4096) -> list:
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, limit)
        if split_at <= 0:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


# ---------------------------------------------------------------------------
# Claude CLI
# ---------------------------------------------------------------------------
CLAUDE_TOOLS = "Read,Edit,Write,Grep,Glob,Bash"


def _kill_current_proc():
    """Kill current Claude subprocess — вызывается при asyncio timeout."""
    with _current_proc_lock:
        proc = _current_proc
    if proc is None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        log.warning("Killed stuck Claude subprocess (pid=%d)", proc.pid)
    except (ProcessLookupError, PermissionError):
        try:
            proc.kill()
        except (ProcessLookupError, PermissionError):
            pass


def _call_claude_once(full_prompt: str, extra_flags=None, timeout_override=None):
    """GPT-5.5 via openai-oauth proxy (localhost:10531)."""
    from openai import OpenAI
    effective_timeout = timeout_override or CLAUDE_TIMEOUT
    try:
        client = OpenAI(
            base_url="http://127.0.0.1:10531/v1",
            api_key="dummy",
            timeout=effective_timeout,
        )
        response = client.chat.completions.create(
            model="gpt-5.5",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": full_prompt},
            ],
            max_tokens=4096,
        )
        answer = response.choices[0].message.content
        if not answer:
            log.warning("Empty response from GPT-5.5")
            return False, ""
        answer = answer.strip()
        return (True, answer) if answer else (False, "")
    except Exception as e:
        log.error("GPT call error: %s", e, exc_info=True)
        return False, ""


def _call_claude_sync(full_prompt: str, extra_flags=None):
    def _once(prompt: str):
        for attempt in range(2):
            ok, text = _call_claude_once(prompt, extra_flags=extra_flags)
            if ok:
                return True, text
            if text == "TIMEOUT":
                return False, "Таймаут (10 мин). Разбей задачу на части — справимся."
            if attempt == 0:
                log.info("Claude attempt 1 failed, retrying...")
                time.sleep(3)
        return False, "Что-то пошло не так. Попробуй ещё раз через минуту."

    # Двухпроходной вызов с поддержкой параллельных суб-агентов
    return two_pass_call(full_prompt, _once)


async def ask_claude(user_text: str, image_path: str = None, user_id: int | None = None):
    global _claude_executor
    hist = history_prompt(user_id)

    extra_flags = None
    is_photo = False

    if image_path:
        full_prompt = ""  # Без истории для фото
        is_photo = True
        caption = user_text or "Опиши что на этом изображении"
        full_prompt += (
            f"Пользователь прислал скриншот/фото.\n"
            f"ПЕРВЫМ ДЕЛОМ прочитай файл: {image_path}\n"
            f"Затем кратко ответь на запрос. НЕ используй другие инструменты, только Read для этого файла.\n\n"
            f"Запрос: {caption}"
        )
        # Для фото: короткий таймаут, мало turns, только Read
        extra_flags = ["--max-turns", "5", "--allowedTools", "Read"]
    else:
        full_prompt = f"История диалога:\n{hist}\n\n" if hist else ""
        full_prompt += f"Влад: {user_text}"

    if len(full_prompt) > MAX_PROMPT_CHARS:
        if hist:
            user_part = full_prompt[len(hist):]
            max_hist = MAX_PROMPT_CHARS - len(user_part)
            full_prompt = (hist[-max_hist:] + user_part) if max_hist > 0 else user_part[-MAX_PROMPT_CHARS:]
        else:
            full_prompt = full_prompt[-MAX_PROMPT_CHARS:]
        log.warning("Prompt truncated to %d chars", len(full_prompt))

    loop = asyncio.get_running_loop()

    if is_photo:
        timeout = CLAUDE_PHOTO_TIMEOUT + 30  # 90 сек жёсткий лимит
        call_fn = lambda: _call_claude_once(full_prompt, extra_flags=extra_flags,
                                             timeout_override=CLAUDE_PHOTO_TIMEOUT)
    else:
        timeout = CLAUDE_TIMEOUT + 60  # 660 сек жёсткий лимит
        call_fn = lambda: _call_claude_sync(full_prompt, extra_flags=extra_flags)

    try:
        return await asyncio.wait_for(
            loop.run_in_executor(_claude_executor, call_fn),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        label = "Photo" if is_photo else "Claude"
        log.error("%s hard timeout (%d sec) — killing proc and resetting executor", label, timeout)
        _kill_current_proc()
        # Создаём НОВЫЙ executor под локом — защита от race condition при параллельных запросах
        with _executor_lock:
            old_executor = _claude_executor
            _claude_executor = ThreadPoolExecutor(max_workers=1)
        try:
            old_executor.shutdown(wait=False)
        except Exception:
            pass
        if is_photo:
            return False, "Таймаут обработки фото. Попробуй ещё раз или опиши текстом."
        return False, "Таймаут. Попробуй ещё раз или разбей задачу на части."
    except asyncio.CancelledError:
        log.error("ask_claude cancelled")
        _kill_current_proc()
        return False, "Запрос был отменён."
    except Exception as e:
        log.error("ask_claude unexpected error: %s", e, exc_info=True)
        _kill_current_proc()
        return False, "Внутренняя ошибка. Попробуй ещё раз."


# ---------------------------------------------------------------------------
# Helpers — статус ботов
# ---------------------------------------------------------------------------
def _bot_status_line(key: str) -> str:
    b = BOTS_REGISTRY[key]
    # Проверяем PID
    alive = False
    pid_str = ""
    pid_file = Path(b["pid_file"])
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            alive = True
            pid_str = f" PID:{pid}"
        except (ValueError, ProcessLookupError, PermissionError):
            pass
    # Heartbeat
    hb_file = Path(b["heartbeat"])
    hb_str = ""
    if hb_file.exists():
        try:
            hb = datetime.fromisoformat(hb_file.read_text().strip())
            age_min = int((datetime.now() - hb).total_seconds() / 60)
            hb_str = f" hb:{age_min}м"
        except Exception:
            pass
    status = "✅" if alive else "❌"
    return f"{status} {b['label']} ({b['handle']}){pid_str}{hb_str} — {b['role']}"


# ---------------------------------------------------------------------------
# Access check
# ---------------------------------------------------------------------------
def is_allowed(update: Update) -> bool:
    return update.effective_user and update.effective_user.id == ALLOWED_USER


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    await update.message.reply_text(
        "Привет! Я Костя — программист-архитектор.\n\n"
        "Помогаю с кодом, дебажу ботов, читаю скрины ошибок, создаю новых ботов.\n\n"
        "Команды:\n"
        "/bots — статус всех ботов\n"
        "/inspect <имя> — логи бота (vasily/masha/beast/kostya)\n"
        "/newbot — создать нового бота\n"
        "/status — мой статус\n"
        "/clear — очистить историю\n\n"
        "Присылай код, скрины, задачи — разберёмся."
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    uptime = datetime.now() - START_TIME
    hours, rem = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(rem, 60)
    await update.message.reply_text(
        f"Костя онлайн\n"
        f"PID: {os.getpid()} | Uptime: {hours}ч {minutes}м {seconds}с\n"
        f"История: {len(user_history)} сообщений\n"
        f"Модель: gpt-5.5"
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    uid = update.effective_user.id
    user_history.clear()
    _save_history()
    sm_clear_history(uid, "kostya")
    await update.message.reply_text("История очищена. Начнём с чистого листа.")


async def cmd_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статус всех ботов из реестра."""
    if not is_allowed(update):
        return
    lines = ["Статус ботов:\n"]
    for key in BOTS_REGISTRY:
        try:
            lines.append(_bot_status_line(key))
        except Exception as e:
            lines.append(f"? {key}: ошибка ({e})")
    await update.message.reply_text("\n".join(lines))


async def cmd_inspect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать последние логи бота. Использование: /inspect vasily"""
    if not is_allowed(update):
        return
    args = context.args
    if not args:
        names = ", ".join(BOTS_REGISTRY.keys())
        await update.message.reply_text(f"Использование: /inspect <имя>\nДоступные: {names}")
        return
    bot_key = args[0].lower().strip("@")
    if bot_key not in BOTS_REGISTRY:
        names = ", ".join(BOTS_REGISTRY.keys())
        await update.message.reply_text(f"Не знаю такого бота. Доступные: {names}")
        return
    b = BOTS_REGISTRY[bot_key]
    log_file = Path(b["log_file"])
    if not log_file.exists():
        await update.message.reply_text(f"Лог файл не найден: {log_file}")
        return
    try:
        result = subprocess.run(
            ["tail", "-30", str(log_file)],
            capture_output=True, text=True, timeout=5
        )
        tail = result.stdout.strip()
        if not tail:
            tail = "(лог пустой)"
        status = _bot_status_line(bot_key)
        reply = f"{status}\n\n```\n{tail[-3000:]}\n```"
        await update.message.reply_text(reply, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Ошибка чтения лога: {e}")


async def cmd_newbot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запустить Claude для создания нового бота."""
    if not is_allowed(update):
        return
    args = context.args
    if not args:
        await update.message.reply_text(
            "Создам нового бота через диалог с Claude.\n\n"
            "Скажи: /newbot <имя> <роль>\n"
            "Например: /newbot analyst анализатор новостей\n\n"
            "Токен нужно будет получить через @BotFather и дать мне."
        )
        return

    bot_name = args[0]
    role = " ".join(args[1:]) if len(args) > 1 else "ассистент"

    prompt = (
        f"Влад хочет создать нового Telegram бота.\n"
        f"Имя: {bot_name}\n"
        f"Роль: {role}\n\n"
        f"Твоя задача:\n"
        f"1. Создай папку {WORKING_DIR}/{bot_name}-bot/\n"
        f"2. Создай telegram_bot.py — используй шаблон бота который ты знаешь\n"
        f"3. Создай requirements.txt\n"
        f"4. Создай ~/Library/LaunchAgents/com.vladimir.{bot_name}-bot.plist\n"
        f"5. Создай ~/{bot_name}-launcher.sh и сделай chmod +x\n"
        f"6. Скажи Владу:\n"
        f"   - Какой ENV ключ использовать для токена\n"
        f"   - Что нужно создать .env файл с токеном от @BotFather\n"
        f"   - Как запустить: launchctl load + kickstart\n\n"
        f"ВАЖНО: .env с токеном НЕ создавай — его даст Влад.\n"
        f"Модель: gpt-5.5 via openai-oauth proxy\n"
        f"Структуру шаблона telegram_bot.py ты знаешь — используй её."
    )

    thinking_msg = await update.message.reply_text(f"Создаю бота {bot_name}... это займёт минуту.")
    ok, answer = await ask_claude(prompt)
    try:
        await thinking_msg.delete()
    except Exception:
        pass
    if ok and answer:
        user_history.append({"role": "assistant", "text": answer})
        _save_history()
        for chunk in _split_message(answer):
            await update.message.reply_text(chunk)
    else:
        await update.message.reply_text(answer or "Ошибка при создании бота.")


async def _thinking_ticker(msg, start: float, prefix: str = "⚙️ Костя работает"):
    """Обновляет сообщение каждые 5 сек — показывает сколько времени идёт обработка."""
    try:
        while True:
            await asyncio.sleep(5)
            elapsed = int(time.monotonic() - start)
            if elapsed > CLAUDE_TIMEOUT + 30:
                break
            try:
                await msg.edit_text(f"{prefix}... {elapsed} сек")
            except Exception as e:
                if "message is not modified" in str(e).lower():
                    continue
                break
    except asyncio.CancelledError:
        pass


PHOTO_DOWNLOAD_TIMEOUT = 30  # макс 30 сек на скачивание фото с Telegram


async def _process_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_text: str,
    image_path: str = None,
    thinking_prefix: str = "⚙️ Костя работает",
):
    """Общая логика обработки запроса (текст или фото). Задачи 2+3."""
    global _processing, _last_message_time, _processing_started

    async with _rate_limit_lock:
        elapsed = time.monotonic() - _last_message_time
        if elapsed < RATE_LIMIT_SEC:
            await asyncio.sleep(RATE_LIMIT_SEC - elapsed)

    async with _processing_lock:
        if _processing:
            if _processing_started > 0 and (time.monotonic() - _processing_started) > PROCESSING_HARD_RESET:
                log.error("Force-resetting stale _processing lock")
                _processing = False
                _processing_started = 0.0
            else:
                await update.message.reply_text("Ещё обрабатываю предыдущий запрос, подожди.")
                return
        _processing = True
        _processing_started = time.monotonic()

    thinking_msg = None
    _ticker_task = None
    try:
        _t_start = time.monotonic()
        thinking_msg = await update.message.reply_text(f"{thinking_prefix}... 0 сек")
        _ticker_task = asyncio.create_task(_thinking_ticker(thinking_msg, _t_start, prefix=thinking_prefix))
        uid = update.effective_user.id
        log_prefix = "[PHOTO] " if image_path else ""
        _log_conversation("user", f"{log_prefix}{user_text}", uid)
        user_history.append({"role": "user", "text": f"{log_prefix}{user_text}"})
        save_message(uid, "kostya", "user", f"{log_prefix}{user_text[:5000]}")

        result = await ask_claude(user_text, image_path=image_path, user_id=uid)
        if not isinstance(result, tuple) or len(result) != 2:
            log.error("ask_claude returned invalid result type: %s", type(result))
            raise ValueError(f"Invalid ask_claude result: {result!r}")
        ok, answer = result

        if _ticker_task:
            _ticker_task.cancel()
        if thinking_msg:
            try:
                await thinking_msg.delete()
            except Exception:
                pass
            thinking_msg = None

        if ok and answer:
            user_history.append({"role": "assistant", "text": answer})
            _save_history()
            save_message(uid, "kostya", "assistant", answer[:5000])
            try:
                extract_facts_from_exchange(uid, "kostya", user_text, answer)
            except Exception as e:
                log.warning("Fact extraction failed (non-blocking): %s", e)
            _log_conversation("assistant", answer)
            for chunk in _split_message(answer):
                try:
                    await update.message.reply_text(chunk, parse_mode="Markdown")
                except Exception:
                    await update.message.reply_text(chunk)
        else:
            err_msg = answer or ("Не удалось проанализировать фото." if image_path else "Что-то пошло не так. Попробуй ещё раз.")
            await update.message.reply_text(err_msg)
    except Exception as e:
        log.error("_process_request error: %s", e, exc_info=True)
        if _ticker_task:
            _ticker_task.cancel()
        if thinking_msg:
            try:
                await thinking_msg.delete()
            except Exception:
                pass
        await update.message.reply_text("Ошибка обработки запроса.")
    finally:
        async with _rate_limit_lock:
            _last_message_time = time.monotonic()
        async with _processing_lock:
            _processing = False
            _processing_started = 0.0


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    user_text = (update.message.text or "").strip()
    if not user_text:
        return
    await _process_request(update, context, user_text)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    # Скачиваем фото сначала, потом передаём в _process_request
    thinking_msg = await update.message.reply_text("📸 Обрабатываю фото... 0 сек")
    _ticker_task = asyncio.create_task(_thinking_ticker(thinking_msg, time.monotonic(), prefix="📸 Обрабатываю фото"))
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        photo_path = PHOTO_DIR / f"photo_{ts}_{photo.file_id[-8:]}.jpg"
        try:
            await asyncio.wait_for(
                file.download_to_drive(str(photo_path)),
                timeout=PHOTO_DOWNLOAD_TIMEOUT,
            )
        except asyncio.TimeoutError:
            log.error("Photo download timed out after %d sec", PHOTO_DOWNLOAD_TIMEOUT)
            _ticker_task.cancel()
            try:
                await thinking_msg.delete()
            except Exception:
                pass
            await update.message.reply_text("⏱ Не смог скачать фото — Telegram тормозит. Попробуй ещё раз.")
            return
        log.info("Photo saved: %s", photo_path)
    except Exception as e:
        log.error("Photo download error: %s", e, exc_info=True)
        _ticker_task.cancel()
        try:
            await thinking_msg.delete()
        except Exception:
            pass
        await update.message.reply_text("Ошибка скачивания фото.")
        return

    _ticker_task.cancel()
    try:
        await thinking_msg.delete()
    except Exception:
        pass

    caption = (update.message.caption or "").strip()
    user_text = caption or "Что на этом изображении? Если это код или ошибка — проанализируй."
    await _process_request(update, context, user_text, image_path=str(photo_path), thinking_prefix="📸 Анализирую фото")


DOCUMENT_TEXT_EXTENSIONS = {'.py', '.js', '.ts', '.txt', '.json', '.md', '.log', '.csv', '.yaml', '.yml', '.sh', '.html', '.css'}


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка документов — текстовые форматы читаем и передаём в Claude."""
    if not is_allowed(update):
        return
    doc = update.message.document
    if not doc:
        return
    file_name = doc.file_name or "document"
    ext = Path(file_name).suffix.lower()

    if ext not in DOCUMENT_TEXT_EXTENSIONS:
        await update.message.reply_text(
            f"Этот формат файла я не умею читать. Поддерживаю: {', '.join(sorted(DOCUMENT_TEXT_EXTENSIONS))}"
        )
        return

    thinking_msg = await update.message.reply_text(f"📄 Читаю {file_name}...")
    try:
        file = await context.bot.get_file(doc.file_id)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        tmp_path = PHOTO_DIR / f"doc_{ts}_{doc.file_id[-8:]}{ext}"
        await asyncio.wait_for(
            file.download_to_drive(str(tmp_path)),
            timeout=PHOTO_DOWNLOAD_TIMEOUT,
        )
        try:
            file_content = tmp_path.read_text(encoding="utf-8", errors="replace")
            if len(file_content) > 40000:
                file_content = file_content[:40000] + "\n... (файл обрезан до 40000 символов)"
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
    except asyncio.TimeoutError:
        try:
            await thinking_msg.delete()
        except Exception:
            pass
        await update.message.reply_text("⏱ Не смог скачать файл. Попробуй ещё раз.")
        return
    except Exception as e:
        log.error("Document download error: %s", e, exc_info=True)
        try:
            await thinking_msg.delete()
        except Exception:
            pass
        await update.message.reply_text(f"Ошибка чтения файла: {e}")
        return

    try:
        await thinking_msg.delete()
    except Exception:
        pass

    caption = (update.message.caption or "").strip()
    user_text = (
        f"Влад прислал файл: {file_name}\n"
        f"{'Запрос: ' + caption + chr(10) if caption else ''}"
        f"Содержимое файла:\n```\n{file_content[:40000]}\n```"
    )
    await _process_request(update, context, user_text, thinking_prefix="⚙️ Анализирую файл")


async def error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    err = context.error
    if isinstance(err, (NetworkError, TimedOut)):
        log.warning("Network error: %s", err)
        return
    if isinstance(err, Conflict):
        log.error("Conflict (duplicate instance). Shutting down.")
        os.kill(os.getpid(), signal.SIGTERM)
        return
    log.error("Unhandled error: %s", err, exc_info=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not BOT_TOKEN:
        log.error("KOSTYA_BOT_TOKEN not set in .env")
        sys.exit(1)

    acquire_lock()
    write_pid()
    _load_history()

    log.info("Starting Kostya bot (PID %d)", os.getpid())

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("bots", cmd_bots))
    app.add_handler(CommandHandler("inspect", cmd_inspect))
    app.add_handler(CommandHandler("newbot", cmd_newbot))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    app.job_queue.run_repeating(heartbeat_job, interval=3600, first=10)  # 1 hour

    log.info("Kostya bot polling started.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
