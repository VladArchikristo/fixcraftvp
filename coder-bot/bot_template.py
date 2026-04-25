#!/usr/bin/env python3
"""
Шаблон нового бота — используется командой /newbot в Косте.
"""

BOT_TEMPLATE = '''#!/usr/bin/env python3
"""
{BOT_LABEL} — {BOT_ROLE}
Создан Костей {CREATED_DATE}
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
from pathlib import Path
from datetime import datetime
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import json
import tempfile

from dotenv import load_dotenv
from telegram import Update
from telegram.error import Conflict, NetworkError, TimedOut
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes,
)

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")

BOT_TOKEN = os.getenv("{ENV_TOKEN_KEY}", "")
ALLOWED_USER = 244710532
CLAUDE_PATH = "/Users/vladimirprihodko/.local/bin/claude"
WORKING_DIR = "/Users/vladimirprihodko/Папка тест/fixcraftvp/"
CLAUDE_TIMEOUT = 600
RATE_LIMIT_SEC = 3
MAX_PROMPT_CHARS = 60000
MODEL = "{MODEL}"

LOG_DIR = Path.home() / "logs"
LOG_DIR.mkdir(exist_ok=True)
PID_FILE = LOG_DIR / "{BOT_ID}-bot.pid"
HEARTBEAT_FILE = LOG_DIR / "{BOT_ID}-heartbeat"
LOCK_FILE = LOG_DIR / "{BOT_ID}-bot.lock"

PHOTO_DIR = SCRIPT_DIR / "data" / "photos"
PHOTO_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = """{SYSTEM_PROMPT}"""

START_TIME = datetime.now()
_claude_executor = ThreadPoolExecutor(max_workers=1)
_processing = False
_processing_lock = asyncio.Lock()
_last_message_time: float = 0.0
_rate_limit_lock = asyncio.Lock()


def _get_claude_env() -> dict:
    home = Path.home()
    nvm_node_bin = ""
    nvm_dir = home / ".nvm" / "versions" / "node"
    if nvm_dir.exists():
        versions = sorted(nvm_dir.iterdir(), reverse=True)
        if versions:
            nvm_node_bin = str(versions[0] / "bin")
    base_path = os.environ.get("PATH", "/usr/bin:/usr/local/bin")
    extra = f"{{home}}/.local/bin:{{nvm_node_bin}}:{{home}}/.bun/bin" if nvm_node_bin else f"{{home}}/.local/bin:{{home}}/.bun/bin"
    env = {{
        "HOME": str(home),
        "PATH": f"{{extra}}:{{base_path}}",
        "USER": os.environ.get("USER", ""),
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        "TERM": os.environ.get("TERM", "xterm-256color"),
    }}
    tmpdir = os.environ.get("TMPDIR")
    if tmpdir:
        env["TMPDIR"] = tmpdir
    return env


_log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.setFormatter(_log_formatter)
_file_handler = RotatingFileHandler(
    LOG_DIR / "{BOT_ID}-bot-main.log", maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_file_handler.setFormatter(_log_formatter)
logging.basicConfig(level=logging.INFO, handlers=[_stdout_handler, _file_handler])
log = logging.getLogger("{BOT_ID}")

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


def write_heartbeat():
    HEARTBEAT_FILE.write_text(datetime.now().isoformat())


async def heartbeat_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        write_heartbeat()
    except Exception as e:
        log.error("Heartbeat write failed: %s", e)


HISTORY_FILE = SCRIPT_DIR / "history.json"
user_history: deque = deque(maxlen=10)
CONVERSATION_LOG = SCRIPT_DIR / "conversation_log.jsonl"


def _log_conversation(role: str, text: str, user_id=None):
    entry = {{"ts": datetime.now().isoformat(), "role": role, "user_id": user_id, "text": text[:5000]}}
    try:
        with open(CONVERSATION_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\\n")
    except Exception as e:
        log.warning("Failed to write conversation log: %s", e)


def _load_history():
    if not HISTORY_FILE.exists():
        return
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("history is not a list")
        for item in data[-30:]:
            if isinstance(item, dict) and "role" in item and "text" in item:
                user_history.append(item)
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


def history_prompt() -> str:
    if not user_history:
        return ""
    lines = []
    total_chars = 0
    for msg in reversed(list(user_history)):
        role = "Влад" if msg["role"] == "user" else "{BOT_LABEL}"
        line = f"{{role}}: {{msg[\'text\'][:1000]}}"
        total_chars += len(line)
        if total_chars > 8000:
            break
        lines.append(line)
    lines.reverse()
    return "\\n".join(lines)


def _split_message(text: str, limit: int = 4096) -> list:
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split_at = text.rfind("\\n", 0, limit)
        if split_at <= 0:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\\n")
    return chunks


CLAUDE_TOOLS = "Read,Edit,Write,Grep,Glob,Bash"


def _call_claude_once(full_prompt: str, extra_flags=None):
    cmd = [
        CLAUDE_PATH, "-p",
        "--model", MODEL,
        "--output-format", "text",
        "--system-prompt", SYSTEM_PROMPT,
        "--allowedTools", CLAUDE_TOOLS,
        "--permission-mode", "bypassPermissions",
    ]
    if extra_flags:
        cmd.extend(extra_flags)
    proc = None
    try:
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=WORKING_DIR, env=_get_claude_env(), text=True, start_new_session=True,
        )
        stdout, stderr = proc.communicate(input=full_prompt, timeout=CLAUDE_TIMEOUT)
        if proc.returncode != 0:
            log.error("Claude exited %d: %s", proc.returncode, stderr.strip())
            return False, ""
        answer = stdout.strip()
        return (True, answer) if answer else (False, "")
    except subprocess.TimeoutExpired:
        if proc:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                try:
                    proc.kill()
                except (ProcessLookupError, PermissionError):
                    pass
            try:
                proc.wait(timeout=5)
            except (ChildProcessError, subprocess.TimeoutExpired):
                pass
        return False, "TIMEOUT"
    except Exception as e:
        log.error("Claude call error: %s", e)
        return False, ""


def _call_claude_sync(full_prompt: str, extra_flags=None):
    for attempt in range(2):
        ok, text = _call_claude_once(full_prompt, extra_flags=extra_flags)
        if ok:
            return True, text
        if text == "TIMEOUT":
            return False, "Таймаут. Разбей задачу на части."
        if attempt == 0:
            time.sleep(3)
    return False, "Что-то пошло не так. Попробуй ещё раз."


async def ask_claude(user_text: str, image_path: str = None):
    hist = history_prompt()
    full_prompt = f"История диалога:\\n{{hist}}\\n\\n" if hist else ""
    if image_path:
        caption = user_text or "Опиши что на этом изображении"
        full_prompt += (
            f"Пользователь прислал изображение. "
            f"Используй Read для файла: {{image_path}}\\n\\n"
            f"Запрос: {{caption}}"
        )
    else:
        full_prompt += f"Влад: {{user_text}}"

    if len(full_prompt) > MAX_PROMPT_CHARS:
        full_prompt = full_prompt[-MAX_PROMPT_CHARS:]

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_claude_executor, lambda: _call_claude_sync(full_prompt))


def is_allowed(update: Update) -> bool:
    return update.effective_user and update.effective_user.id == ALLOWED_USER


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    await update.message.reply_text(
        "Привет! Я {BOT_LABEL} — {BOT_ROLE}\\n\\n"
        "Команды:\\n"
        "/status — статус\\n"
        "/clear — очистить историю\\n\\n"
        "Пиши задачи, пришли код или скриншот."
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    uptime = datetime.now() - START_TIME
    h, rem = divmod(int(uptime.total_seconds()), 3600)
    m, s = divmod(rem, 60)
    await update.message.reply_text(
        f"{{h}}ч {{m}}м {{s}}с онлайн | PID {{os.getpid()}} | {{len(user_history)}} сообщений | модель: {{MODEL}}"
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    user_history.clear()
    _save_history()
    await update.message.reply_text("История очищена.")


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
            except Exception:
                break
    except asyncio.CancelledError:
        pass


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _processing, _last_message_time
    if not is_allowed(update):
        return
    user_text = (update.message.text or "").strip()
    if not user_text:
        return

    async with _rate_limit_lock:
        elapsed = time.monotonic() - _last_message_time
        if elapsed < RATE_LIMIT_SEC:
            await asyncio.sleep(RATE_LIMIT_SEC - elapsed)

    async with _processing_lock:
        if _processing:
            await update.message.reply_text("Ещё обрабатываю предыдущий запрос.")
            return
        _processing = True

    thinking_msg = None
    _ticker_task = None
    try:
        _t_start = time.monotonic()
        thinking_msg = await update.message.reply_text("⚙️ Костя работает... 0 сек")
        _ticker_task = asyncio.create_task(_thinking_ticker(thinking_msg, _t_start))
        _log_conversation("user", user_text, update.effective_user.id)
        user_history.append({{"role": "user", "text": user_text}})
        ok, answer = await ask_claude(user_text)
        if _ticker_task:
            _ticker_task.cancel()
        if thinking_msg:
            try:
                await thinking_msg.delete()
            except Exception:
                pass
            thinking_msg = None
        if ok and answer:
            user_history.append({{"role": "assistant", "text": answer}})
            _save_history()
            _log_conversation("assistant", answer)
            for chunk in _split_message(answer):
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(answer or "Ошибка. Попробуй ещё раз.")
    except Exception as e:
        log.error("handle_message error: %s", e, exc_info=True)
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


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _processing
    if not is_allowed(update):
        return

    async with _processing_lock:
        if _processing:
            await update.message.reply_text("Ещё обрабатываю предыдущий запрос.")
            return
        _processing = True

    thinking_msg = None
    _ticker_task = None
    try:
        _t_start = time.monotonic()
        thinking_msg = await update.message.reply_text("⚙️ Костя работает... 0 сек")
        _ticker_task = asyncio.create_task(_thinking_ticker(thinking_msg, _t_start))
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        photo_path = PHOTO_DIR / f"photo_{{ts}}_{{photo.file_id[-8:]}}.jpg"
        await file.download_to_drive(str(photo_path))

        caption = (update.message.caption or "").strip()
        user_text = caption or "Что на этом изображении? Если это код или ошибка — проанализируй."
        _log_conversation("user", f"[PHOTO] {{user_text}}", update.effective_user.id)
        user_history.append({{"role": "user", "text": f"[PHOTO] {{user_text}}"}})

        ok, answer = await ask_claude(user_text, image_path=str(photo_path))
        if _ticker_task:
            _ticker_task.cancel()
        if thinking_msg:
            try:
                await thinking_msg.delete()
            except Exception:
                pass
            thinking_msg = None
        if ok and answer:
            user_history.append({{"role": "assistant", "text": answer}})
            _save_history()
            _log_conversation("assistant", answer)
            for chunk in _split_message(answer):
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(answer or "Не удалось проанализировать фото.")
    except Exception as e:
        log.error("handle_photo error: %s", e, exc_info=True)
        if _ticker_task:
            _ticker_task.cancel()
        if thinking_msg:
            try:
                await thinking_msg.delete()
            except Exception:
                pass
        await update.message.reply_text("Ошибка при обработке фото.")
    finally:
        async with _processing_lock:
            _processing = False


async def error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    err = context.error
    if isinstance(err, (NetworkError, TimedOut)):
        log.warning("Network error: %s", err)
        return
    if isinstance(err, Conflict):
        log.error("Conflict — shutting down.")
        os.kill(os.getpid(), signal.SIGTERM)
        return
    log.error("Unhandled error: %s", err, exc_info=True)


def main():
    if not BOT_TOKEN:
        log.error("{ENV_TOKEN_KEY} not set in .env")
        sys.exit(1)
    acquire_lock()
    write_pid()
    _load_history()
    log.info("Starting {BOT_LABEL} bot (PID %d)", os.getpid())
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    app.job_queue.run_repeating(heartbeat_job, interval=3600, first=10)  # 1 hour
    log.info("{BOT_LABEL} bot polling started.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
'''
