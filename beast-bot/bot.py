#!/usr/bin/env python3
"""
Beast v11 — Claude Code Telegram Bot (production-grade)
- Singleton lock via fcntl.flock
- Error handler: 409 Conflict auto-exit, NetworkError retry
- Atomic heartbeat, proper shutdown cleanup
- Retry logic for Telegram API calls
- Message queue (max 3) with worker — no dropped messages
- Streaming stdout with partial response on timeout
- Photo download + forwarding to Claude CLI
- Process group kill for subprocess tree
- Markdown support with fallback, chunk dedup
- Graceful signal handling (SIGTERM/SIGINT)
- Connection pool tuning for httpx
- Numbered log rotation (3 backups)
- History persistence across restarts
- System prompt + allowedTools + bypassPermissions
- Full stderr capture for debugging
- Three-level shared memory (facts + sessions + cross-bot)
- Haiku AI fact extraction after each response
"""

from __future__ import annotations

import asyncio
from typing import Optional
import fcntl
import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime
from collections import deque
from pathlib import Path

import sys
sys.path.insert(0, '/Users/vladimirprihodko/Папка тест/fixcraftvp/shared-memory')
from shared_memory import save_message, build_memory_prompt, save_session_summary
from fact_extractor import extract_facts_from_exchange

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import Conflict, NetworkError, TimedOut, RetryAfter, BadRequest
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

load_dotenv(Path(__file__).parent / ".env")

TOKEN = os.environ["BEAST_BOT_TOKEN"]
ALLOWED_USER = 244710532
CLAUDE_PATH = "/Users/vladimirprihodko/.local/bin/claude"
CLAUDE_CWD = "/Users/vladimirprihodko/Папка тест/fixcraftvp/beast-bot/"
LOGS_DIR = Path.home() / "logs"
LOCK_FILE = LOGS_DIR / "beast-bot.lock"
PID_FILE = LOGS_DIR / "beast-bot.pid"
HEARTBEAT_FILE = LOGS_DIR / "beast-heartbeat"
TIMEOUT_SEC = 300
HEARTBEAT_INTERVAL = 60
HISTORY_SIZE = 6
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0
MAX_CONSECUTIVE_ERRORS = 5
AUTH_ERROR_MARKERS = ["not logged in", "authentication_failed", "Please run /login"]
RATE_LIMIT_WINDOW = 5
MAX_PROMPT_CHARS = 50000
CLAUDE_MODEL = os.environ.get("BEAST_MODEL", "claude-sonnet-4-6")
CLAUDE_TOOLS = "Read,Edit,Write,Grep,Glob,Bash"
HISTORY_PERSIST_FILE = Path(__file__).parent / "history_state.json"
OBSIDIAN_MEMORY = Path.home() / "ObsidianVault" / "ClaudeClaw-Memory" / "beast-memory.md"

# Full conversation log (never truncated, appends forever)
CONVERSATION_LOG = Path(__file__).parent / "conversation_log.jsonl"
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB

BASE_SYSTEM_PROMPT = (
    "Ты Beast (@Antropic_BeastBot) — главный AI-ассистент Владимира. "
    "Точка входа для всех задач. Доступ к Claude Code CLI, инструменты: Read, Edit, Write, Grep, Glob, Bash.\n\n"
    "ХОЗЯИН: Владимир (Влад), предприниматель, Telegram ID 244710532. "
    "FixCraft VP — handyman бизнес в Charlotte NC. Суперпроект: Остров → научный хаб.\n\n"
    "БОТЫ: Костя (@KostyaCoderBot) — программист | Маша (@masha_marketer_bot) — маркетолог | "
    "Василий (@vasily_trader_bot) — трейдер | Филип (@PhilipThinkerBot) — промт-инженер | "
    "Пётр (@PeterMedBot) — медицина | Зина (@ZinaAstroBot) — астрология\n\n"
    "СТИЛЬ: русский, кратко, по делу. Не начинай с 'Привет!' — сразу к задаче. Markdown для форматирования.\n\n"
    "ПРАВИЛА: не показывай токены/ключи, не делай деструктивных команд без запроса, "
    "git-save только на GitHub (не Vercel)."
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

from logging.handlers import RotatingFileHandler

# Silence httpx to hide bot token from logs
logging.getLogger("httpx").setLevel(logging.WARNING)

LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Rotating file handler: 5 MB per file, keep 3 backups
_log_file = LOGS_DIR / "beast-bot.log"
_file_handler = RotatingFileHandler(
    _log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8",
)
_file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

logging.basicConfig(
    level=logging.INFO,
    handlers=[_file_handler],
)
log = logging.getLogger("beast")

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

start_time: float = 0.0
history: deque = deque(maxlen=HISTORY_SIZE)
heartbeat_task: Optional[asyncio.Task] = None
worker_task: Optional[asyncio.Task] = None
lock_fd = None
message_queue: Optional[asyncio.Queue] = None
MAX_QUEUE_SIZE = 3
active_claude_proc: Optional[subprocess.Popen] = None
_proc_lock = threading.Lock()
consecutive_errors: int = 0
_alert_sent: bool = False
_last_message_time: float = 0.0


def _find_nvm_node_path(home: str) -> str:
    """Find latest nvm node bin path. Returns ':path' or empty string."""
    nvm_dir = Path(home) / ".nvm/versions/node"
    if nvm_dir.exists():
        versions = sorted(
            [d for d in nvm_dir.iterdir() if d.is_dir()],
            key=lambda d: d.name,
            reverse=True,
        )
        if versions:
            return f":{versions[0]}/bin"
    return ""


def _get_claude_env() -> dict:
    """Clean env for Claude CLI — essentials + node/bun paths."""
    home = str(Path.home())
    env = {
        "HOME": home,
        "PATH": os.environ.get("PATH", "/usr/bin:/usr/local/bin")
               + _find_nvm_node_path(home)
               + f":{home}/.local/bin:/opt/homebrew/bin:/usr/local/bin",
        "USER": os.environ.get("USER", ""),
        "LANG": "en_US.UTF-8",
        "TERM": os.environ.get("TERM", "xterm-256color"),
        "SHELL": os.environ.get("SHELL", "/bin/zsh"),
    }
    for key in ("TMPDIR", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME",
                "NODE_PATH", "npm_config_prefix", "BUN_INSTALL"):
        val = os.environ.get(key)
        if val:
            env[key] = val
    return env


def _load_history():
    """Load history from disk on startup."""
    global history
    try:
        if HISTORY_PERSIST_FILE.exists():
            raw = HISTORY_PERSIST_FILE.read_text(encoding="utf-8").strip()
            if not raw:
                log.info("History file empty, starting fresh")
                return
            data = json.loads(raw)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, (list, tuple)) and len(item) == 2:
                        history.append((item[0], item[1]))
                log.info("Loaded %d history entries from disk", len(history))
            else:
                log.warning("History file has unexpected format, starting fresh")
        else:
            log.info("No history file found at %s", HISTORY_PERSIST_FILE)
    except Exception as e:
        log.warning("Failed to load history: %s", e)


def _save_history():
    """Persist current history to disk."""
    try:
        data = list(history)
        HISTORY_PERSIST_FILE.write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as e:
        log.warning("Failed to save history: %s", e)


def _log_conversation(role: str, text: str, user_id: Optional[int] = None):
    """Append a single message to the permanent conversation log."""
    entry = {
        "ts": datetime.now().isoformat(),
        "role": role,
        "user_id": user_id,
        "text": text[:5000],
    }
    try:
        if CONVERSATION_LOG.exists() and CONVERSATION_LOG.stat().st_size > MAX_LOG_SIZE:
            for i in range(3, 1, -1):
                src = CONVERSATION_LOG.parent / f"conversation_log.{i-1}.jsonl"
                dst = CONVERSATION_LOG.parent / f"conversation_log.{i}.jsonl"
                if src.exists():
                    src.rename(dst)
            CONVERSATION_LOG.rename(CONVERSATION_LOG.parent / "conversation_log.1.jsonl")
            log.info("Rotated conversation log (>%d bytes)", MAX_LOG_SIZE)
        with open(CONVERSATION_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        log.warning("Failed to write conversation log: %s", e)


# ---------------------------------------------------------------------------
# Error tracking & Telegram alert
# ---------------------------------------------------------------------------

async def _send_owner_alert(bot, text: str):
    """Send alert to bot owner via Telegram."""
    try:
        await bot.send_message(chat_id=ALLOWED_USER, text=f"⚠️ Beast Alert:\n{text}")
        log.warning("Alert sent to owner: %s", text[:100])
    except Exception as exc:
        log.error("Failed to send alert: %s", exc)


def _check_auth_error(response: str) -> bool:
    """Check if Claude response indicates auth failure."""
    lower = response.lower()
    return any(marker.lower() in lower for marker in AUTH_ERROR_MARKERS)


# ---------------------------------------------------------------------------
# Singleton lock
# ---------------------------------------------------------------------------

def acquire_lock() -> bool:
    """Try to acquire an exclusive lock. Return True on success."""
    global lock_fd
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    lock_fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
        return True
    except OSError:
        log.warning("Another Beast instance holds the lock. Exiting cleanly.")
        lock_fd.close()
        lock_fd = None
        return False


def write_pid():
    PID_FILE.write_text(str(os.getpid()))
    log.info("PID %d written to %s", os.getpid(), PID_FILE)

# ---------------------------------------------------------------------------
# Kill zombie claude processes from previous Beast runs
# ---------------------------------------------------------------------------

def kill_zombie_claude():
    """Kill orphaned claude CLI processes spawned by Beast only (checks CWD match)."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "claude.*-p"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return
        my_pid = os.getpid()
        for line in result.stdout.strip().splitlines():
            try:
                pid = int(line.strip())
            except ValueError:
                continue
            if pid == my_pid:
                continue
            try:
                # Only kill if orphaned (ppid=1) AND was spawned in Beast's CWD
                ps = subprocess.run(
                    ["ps", "-o", "ppid=", "-p", str(pid)],
                    capture_output=True, text=True, timeout=5,
                )
                ppid = int(ps.stdout.strip())
                if ppid != 1:
                    continue
                # Check if process CWD matches Beast's working directory
                lsof = subprocess.run(
                    ["lsof", "-p", str(pid), "-Fn"],
                    capture_output=True, text=True, timeout=5,
                )
                if CLAUDE_CWD not in lsof.stdout:
                    log.debug("Skipping zombie PID %d — not Beast's CWD", pid)
                    continue
                os.kill(pid, signal.SIGKILL)
                log.info("Killed zombie claude PID %d (ppid=1, CWD matched)", pid)
            except (ValueError, ProcessLookupError, subprocess.TimeoutExpired):
                pass
    except Exception as exc:
        log.warning("kill_zombie_claude error: %s", exc)

# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------

async def heartbeat_loop():
    """Write timestamp to heartbeat file every HEARTBEAT_INTERVAL seconds."""
    while True:
        tmp_path = None
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(dir=str(LOGS_DIR), prefix="beast-hb-")
            try:
                os.write(tmp_fd, str(int(time.time())).encode())
            finally:
                os.close(tmp_fd)
            os.replace(tmp_path, str(HEARTBEAT_FILE))
            tmp_path = None
        except Exception as exc:
            log.warning("Heartbeat write error: %s", exc)
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        await asyncio.sleep(HEARTBEAT_INTERVAL)

# ---------------------------------------------------------------------------
# Retry wrapper for Telegram API calls
# ---------------------------------------------------------------------------

def _split_text(text: str, limit: int = 4096) -> list[str]:
    """Split text into chunks respecting the limit."""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = text.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks


async def safe_reply(message, text: str, parse_mode=None) -> None:
    """Send reply with retries and Markdown fallback."""
    chunks = _split_text(text)
    sent = 0
    for attempt in range(MAX_RETRIES):
        try:
            for i in range(sent, len(chunks)):
                await message.reply_text(chunks[i], parse_mode=parse_mode)
                sent = i + 1
            return
        except BadRequest as e:
            if parse_mode and "parse" in str(e).lower():
                log.warning("Markdown parse failed, retrying as plain text")
                parse_mode = None
                sent = 0
                continue
            raise
        except RetryAfter as e:
            log.warning("Rate limited, sleeping %ds", e.retry_after)
            await asyncio.sleep(e.retry_after)
        except (NetworkError, TimedOut) as e:
            delay = RETRY_BASE_DELAY * (2 ** attempt)
            log.warning("Reply failed (attempt %d/%d): %s, retrying in %.1fs",
                        attempt + 1, MAX_RETRIES, e, delay)
            await asyncio.sleep(delay)
    for i in range(sent, len(chunks)):
        await message.reply_text(chunks[i])

# ---------------------------------------------------------------------------
# Build prompt with history context
# ---------------------------------------------------------------------------

def build_system_context() -> str:
    """Build a system-prompt string with memory + recent conversation history."""
    lines = []

    # Трёхуровневая память из shared_memory
    try:
        memory_block = build_memory_prompt(ALLOWED_USER, "beast")
        if memory_block:
            lines.append(memory_block)
    except Exception as e:
        log.warning("Failed to build memory prompt: %s", e)

    # Короткая история из deque
    if history:
        lines.append("\n=== ПОСЛЕДНИЙ ДИАЛОГ ===")
        for role, text in history:
            prefix = "Влад" if role == "user" else "Beast"
            short = text[:500] + "..." if len(text) > 500 else text
            lines.append(f"{prefix}: {short}")

    return "\n".join(lines) if lines else ""

# ---------------------------------------------------------------------------
# Call claude CLI
# ---------------------------------------------------------------------------

async def call_claude(prompt: str) -> str:
    """
    Spawn claude CLI with Popen, parse stream-json output line-by-line.
    Uses process group for clean kill. On timeout returns partial response.
    """
    global active_claude_proc

    session_id = str(uuid.uuid4())
    log.info("Claude call session=%s prompt_len=%d", session_id[:8], len(prompt))

    if len(prompt) > MAX_PROMPT_CHARS:
        prompt = prompt[-MAX_PROMPT_CHARS:]
        log.warning("Prompt truncated to %d chars", MAX_PROMPT_CHARS)

    cmd = [
        CLAUDE_PATH,
        "-p", prompt,
        "--output-format", "stream-json",
        "--verbose",
        "--model", CLAUDE_MODEL,
        "--system-prompt", BASE_SYSTEM_PROMPT,
        "--allowedTools", CLAUDE_TOOLS,
        "--permission-mode", "bypassPermissions",
        "--max-turns", "10",
        "--add-dir", "/Users/vladimirprihodko/Папка тест/fixcraftvp/beast-bot/",
    ]

    ctx = build_system_context()
    if ctx:
        cmd.extend(["--append-system-prompt", ctx])

    loop = asyncio.get_running_loop()

    def _run_subprocess() -> str:
        global active_claude_proc
        env = _get_claude_env()
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=CLAUDE_CWD,
            env=env,
            start_new_session=True,
        )
        with _proc_lock:
            active_claude_proc = proc
        log.info("Spawned claude PID %d (pgid=%d)", proc.pid, os.getpgid(proc.pid))

        # Drain stderr in background thread
        stderr_chunks: list[bytes] = []
        def _drain_stderr():
            try:
                for chunk in iter(lambda: proc.stderr.read(4096), b""):
                    stderr_chunks.append(chunk)
            except Exception:
                pass
        stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
        stderr_thread.start()

        # Read stdout line-by-line, parse stream-json
        result_parts: list[str] = []
        final_result: Optional[str] = None
        timed_out = False
        deadline = time.monotonic() + TIMEOUT_SEC

        try:
            for raw_line in proc.stdout:
                if time.monotonic() > deadline:
                    timed_out = True
                    break
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if obj.get("type") == "result":
                    result_text = obj.get("result", "")
                    if result_text:
                        final_result = result_text

                if obj.get("type") == "content_block_delta":
                    delta = obj.get("delta", {})
                    if delta.get("type") == "text_delta":
                        result_parts.append(delta.get("text", ""))
        except Exception as exc:
            log.warning("Error reading claude stdout: %s", exc)

        if timed_out:
            log.warning("Claude PID %d timed out after %ds, killing",
                        proc.pid, TIMEOUT_SEC)
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, OSError):
                try:
                    os.kill(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            proc.wait()
            with _proc_lock:
                active_claude_proc = None
            partial = final_result or "".join(result_parts)
            if partial.strip():
                return partial + f"\n\n[Частичный ответ — таймаут после {TIMEOUT_SEC}с]"
            return f"[Timeout] Claude CLI не ответил за {TIMEOUT_SEC} секунд."

        proc.wait()
        with _proc_lock:
            active_claude_proc = None

        stderr_thread.join(timeout=5)
        stderr_text = b"".join(stderr_chunks).decode("utf-8", errors="replace").strip()

        # Always prefer actual content over exit code — hooks can cause
        # non-zero exit even when Claude returned a valid response.
        if final_result:
            if proc.returncode != 0:
                log.warning("Claude exited %d but result recovered | stderr: %s",
                            proc.returncode, stderr_text[:300] if stderr_text else "(empty)")
            return final_result
        if result_parts:
            if proc.returncode != 0:
                log.warning("Claude exited %d but partial result recovered | stderr: %s",
                            proc.returncode, stderr_text[:300] if stderr_text else "(empty)")
            return "".join(result_parts)

        if proc.returncode != 0:
            log.error("Claude exited %d with NO output | stderr: %s",
                      proc.returncode, stderr_text[:500] if stderr_text else "(empty)")
            err_detail = f" ({stderr_text[:200]})" if stderr_text else ""
            return f"[Error] Claude завершился с кодом {proc.returncode}.{err_detail}"

        return "[Empty] Claude вернул пустой ответ."

    return await loop.run_in_executor(None, _run_subprocess)

# ---------------------------------------------------------------------------
# Access check
# ---------------------------------------------------------------------------

def is_allowed(update: Update) -> bool:
    return update.effective_user and update.effective_user.id == ALLOWED_USER

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, _):
    log.info(">>> cmd_start called, user_id=%s",
             update.effective_user.id if update.effective_user else None)
    if not is_allowed(update):
        return
    await update.message.reply_text(
        "Beast v11 online.\n"
        "Пиши сообщение — я отправлю его в Claude Code CLI и верну ответ."
    )


async def cmd_status(update: Update, _):
    if not is_allowed(update):
        return
    uptime_sec = int(time.time() - start_time)
    hours, remainder = divmod(uptime_sec, 3600)
    minutes, secs = divmod(remainder, 60)
    qsize = message_queue.qsize() if message_queue else 0
    await update.message.reply_text(
        f"Beast v11\n"
        f"PID: {os.getpid()}\n"
        f"Uptime: {hours}h {minutes}m {secs}s\n"
        f"History: {len(history)}/{HISTORY_SIZE} messages\n"
        f"Queue: {qsize}/{MAX_QUEUE_SIZE}\n"
        f"Errors: {consecutive_errors}/{MAX_CONSECUTIVE_ERRORS}\n"
        f"Timeout: {TIMEOUT_SEC}s"
    )


async def cmd_clear(update: Update, _):
    if not is_allowed(update):
        return
    history.clear()
    _save_history()
    await update.message.reply_text("History cleared.")


async def cmd_restart(update: Update, _):
    if not is_allowed(update):
        return
    _save_history()
    await update.message.reply_text("Перезапускаюсь...")
    log.info("Restart requested by user, execv...")
    os.execv(sys.executable, [sys.executable] + sys.argv)


async def cmd_health(update: Update, _):
    if not is_allowed(update):
        return
    uptime_sec = int(time.time() - start_time)
    hours, remainder = divmod(uptime_sec, 3600)
    minutes, secs = divmod(remainder, 60)
    hb_age = "N/A"
    try:
        hb_ts = int(HEARTBEAT_FILE.read_text())
        hb_age = f"{int(time.time()) - hb_ts}s ago"
    except Exception:
        pass
    log_size = "0KB"
    try:
        log_size = f"{CONVERSATION_LOG.stat().st_size / 1024:.1f}KB"
    except Exception:
        pass
    await update.message.reply_text(
        f"Beast v11 Health Check\n"
        f"Uptime: {hours}h {minutes}m {secs}s\n"
        f"PID: {os.getpid()}\n"
        f"Errors in a row: {consecutive_errors}/{MAX_CONSECUTIVE_ERRORS}\n"
        f"Heartbeat: {hb_age}\n"
        f"History: {len(history)}/{HISTORY_SIZE}\n"
        f"Conv log: {log_size}\n"
        f"Queue: {message_queue.qsize() if message_queue else 0}/{MAX_QUEUE_SIZE}\n"
        f"Timeout: {TIMEOUT_SEC}s\n"
        f"Model: {CLAUDE_MODEL}\n"
        f"CWD: {CLAUDE_CWD}"
    )


async def handle_photo(update: Update, context):
    """Handle photo messages — download photo, save to temp file, forward to Claude."""
    if not is_allowed(update):
        return
    caption = update.message.caption or "Опиши это изображение"

    photo_file = await update.message.photo[-1].get_file()
    photo_path = f"/tmp/beast-photo-{uuid.uuid4().hex[:8]}.jpg"
    try:
        await photo_file.download_to_drive(photo_path)
        log.info("Photo downloaded to %s", photo_path)
        prompt = f"[Пользователь отправил фото: {photo_path}]\n{caption}"
        await _process_user_text(update, prompt, cleanup_files=[photo_path])
    except Exception as exc:
        log.error("Failed to download photo: %s", exc)
        await update.message.reply_text(f"Не удалось скачать фото: {exc}")
        try:
            os.unlink(photo_path)
        except OSError:
            pass


SUPPORTED_DOC_EXTENSIONS = {".txt", ".py", ".js", ".ts", ".json", ".md", ".csv", ".yaml", ".yml",
                             ".html", ".css", ".sh", ".toml", ".ini", ".cfg", ".xml", ".sql", ".log",
                             ".env.example", ".jsx", ".tsx", ".go", ".rs", ".java", ".kt", ".swift"}
MAX_DOC_SIZE = 1 * 1024 * 1024  # 1 MB


async def handle_document(update: Update, context):
    """Handle document messages — download text files, forward to Claude."""
    if not is_allowed(update):
        return
    doc = update.message.document
    file_name = doc.file_name or "unknown"
    file_ext = Path(file_name).suffix.lower()

    if file_ext not in SUPPORTED_DOC_EXTENSIONS:
        await update.message.reply_text(
            f"Формат `{file_ext}` не поддерживается.\n"
            f"Поддерживаемые: {', '.join(sorted(SUPPORTED_DOC_EXTENSIONS)[:10])}..."
        )
        return

    if doc.file_size and doc.file_size > MAX_DOC_SIZE:
        await update.message.reply_text(f"Файл слишком большой ({doc.file_size // 1024}KB, лимит 1MB).")
        return

    doc_file = await doc.get_file()
    doc_path = f"/tmp/beast-doc-{uuid.uuid4().hex[:8]}-{file_name}"
    try:
        await doc_file.download_to_drive(doc_path)
        log.info("Document downloaded to %s (%s, %d bytes)", doc_path, file_name, doc.file_size or 0)
        caption = update.message.caption or f"Проанализируй файл {file_name}"
        prompt = f"[Пользователь отправил файл: {doc_path}]\n{caption}"
        await _process_user_text(update, prompt, cleanup_files=[doc_path])
    except Exception as exc:
        log.error("Failed to download document: %s", exc)
        await update.message.reply_text(f"Не удалось скачать документ: {exc}")
        try:
            os.unlink(doc_path)
        except OSError:
            pass


async def _process_user_text(update: Update, user_text: str, cleanup_files: list[str] | None = None):
    """Enqueue user message for processing."""
    global _last_message_time
    if message_queue is None:
        return

    now = time.time()
    elapsed = now - _last_message_time
    if elapsed < RATE_LIMIT_WINDOW:
        wait = int(RATE_LIMIT_WINDOW - elapsed)
        await update.message.reply_text(f"Подожди {wait}с.")
        return
    _last_message_time = now

    if message_queue.full():
        await update.message.reply_text(f"Очередь полна ({MAX_QUEUE_SIZE}), подожди...")
        return

    qsize = message_queue.qsize()
    if qsize > 0:
        status_msg = await update.message.reply_text(f"В очереди ({qsize + 1})...")
    else:
        status_msg = await update.message.reply_text("Думаю...")

    task = {
        "update": update,
        "user_text": user_text,
        "cleanup_files": cleanup_files,
        "status_msg": status_msg,
        "enqueued_at": time.time(),
    }
    await message_queue.put(task)


async def _queue_worker():
    """Worker that processes messages from the queue one at a time."""
    global consecutive_errors, _alert_sent

    while True:
        task = await message_queue.get()
        update = task["update"]
        user_text = task["user_text"]
        cleanup_files = task["cleanup_files"]
        status_msg = task["status_msg"]

        try:
            await status_msg.edit_text("Думаю...")
        except Exception:
            pass

        _think_start = time.time()

        async def _update_thinking():
            dots = 1
            _tick = 0
            _bot = update.get_bot()
            _chat_id = update.effective_chat.id
            while True:
                # Telegram typing action expires after ~5s — refresh every 4s
                try:
                    await _bot.send_chat_action(chat_id=_chat_id, action="typing")
                except Exception:
                    pass
                await asyncio.sleep(4)
                _tick += 1
                if _tick % 8 == 0:  # Every ~32s update status message
                    dots = (dots % 5) + 1
                    elapsed = int(time.time() - _think_start)
                    try:
                        await status_msg.edit_text(f"Думаю{'.' * dots} ({elapsed}с)")
                    except Exception:
                        pass

        thinking_task = asyncio.create_task(_update_thinking())

        history.append(("user", user_text))
        _log_conversation("user", user_text, update.effective_user.id)

        # Shared memory: сохраняем сообщение пользователя
        try:
            save_message(ALLOWED_USER, "beast", "user", user_text[:2000])
        except Exception as e:
            log.warning("Failed to save user message to shared memory: %s", e)

        try:
            response = await call_claude(user_text)
        except Exception as exc:
            log.error("call_claude exception: %s", exc, exc_info=True)
            response = f"[Error] {exc}"
        finally:
            thinking_task.cancel()

        # Track consecutive errors
        is_error = response.startswith(("[Error]", "[Timeout]", "[Empty]"))
        if is_error:
            consecutive_errors += 1
            log.warning("Consecutive errors: %d/%d", consecutive_errors, MAX_CONSECUTIVE_ERRORS)
            if _check_auth_error(response) and not _alert_sent:
                _alert_sent = True
                try:
                    bot = update.get_bot()
                    await _send_owner_alert(bot,
                        "Claude CLI не авторизован!\n"
                        "Нужно запустить: claude auth login\n"
                        f"Ответ: {response[:200]}")
                except Exception:
                    pass
            elif consecutive_errors >= MAX_CONSECUTIVE_ERRORS and not _alert_sent:
                _alert_sent = True
                try:
                    bot = update.get_bot()
                    await _send_owner_alert(bot,
                        f"{consecutive_errors} ошибок подряд!\n"
                        f"Последняя: {response[:200]}\n"
                        "Проверь логи: ~/logs/beast-bot.log")
                except Exception:
                    pass
        else:
            if consecutive_errors > 0:
                log.info("Error streak reset (was %d)", consecutive_errors)
            consecutive_errors = 0
            _alert_sent = False

        history.append(("assistant", response))
        _log_conversation("assistant", response, update.effective_user.id)
        _save_history()

        # Shared memory: сохраняем ответ + извлекаем факты (Haiku в фоне)
        try:
            save_message(ALLOWED_USER, "beast", "assistant", response[:2000])
            uid = update.effective_user.id
            extract_facts_from_exchange(uid, "beast", user_text, response)
        except Exception as e:
            log.warning("Failed to save/extract to shared memory: %s", e)

        try:
            await status_msg.delete()
        except Exception:
            pass

        await safe_reply(update.message, response, parse_mode=ParseMode.MARKDOWN)

        if cleanup_files:
            for f in cleanup_files:
                try:
                    os.unlink(f)
                except OSError:
                    pass

        message_queue.task_done()


async def handle_unsupported(update: Update, _):
    """Reply to unsupported message types (documents, voice, stickers, etc.)."""
    if not is_allowed(update):
        return
    msg_type = "файл"
    if update.message.voice or update.message.audio:
        msg_type = "голосовое/аудио"
    elif update.message.video or update.message.video_note:
        msg_type = "видео"
    elif update.message.sticker:
        msg_type = "стикер"
    elif update.message.document:
        msg_type = "документ"
    await update.message.reply_text(
        f"Пока не умею обрабатывать {msg_type}.\n"
        "Отправь текстом или фото."
    )


async def handle_message(update: Update, _):
    log.info(">>> handle_message called, user_id=%s, text=%r",
             update.effective_user.id if update.effective_user else None,
             (update.message.text or "")[:100] if update.message else None)
    if not is_allowed(update):
        log.info(">>> BLOCKED by is_allowed, expected=%d", ALLOWED_USER)
        return

    user_text = update.message.text
    if not user_text:
        return

    await _process_user_text(update, user_text)

# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------

async def post_shutdown(app: Application):
    """Cancel heartbeat, worker, kill active Claude, release lock, clean PID."""
    global heartbeat_task, worker_task, lock_fd, active_claude_proc

    # Save history before shutdown so it persists across restarts
    _save_history()
    log.info("History saved on shutdown (%d entries)", len(history))

    with _proc_lock:
        proc = active_claude_proc
    if proc and proc.poll() is None:
        log.info("Killing active Claude PID %d on shutdown", proc.pid)
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass

    for task in (heartbeat_task, worker_task):
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    if lock_fd is not None:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
            lock_fd = None
        except Exception:
            pass

    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass

    log.info("Beast shutdown complete.")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def _stop_app(app: Application):
    """Gracefully stop the application (used on 409 Conflict)."""
    try:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
    except Exception as exc:
        log.error("Error during graceful stop: %s", exc)
    finally:
        # Exit with 0 so LaunchAgent does not immediately respawn
        os._exit(0)


def main():
    global start_time, heartbeat_task, worker_task, message_queue

    if not acquire_lock():
        sys.exit(0)

    write_pid()
    kill_zombie_claude()

    start_time = time.time()
    message_queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
    _load_history()
    log.info("Beast v11 starting, PID=%d, history=%d", os.getpid(), len(history))

    app = (
        Application.builder()
        .token(TOKEN)
        .post_shutdown(post_shutdown)
        .http_version("1.1")
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(10.0)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("health", cmd_health))
    app.add_handler(CommandHandler("restart", cmd_restart))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(
        filters.VOICE | filters.AUDIO |
        filters.VIDEO | filters.VIDEO_NOTE | filters.Sticker.ALL,
        handle_unsupported,
    ))

    async def error_handler(update, context):
        err = context.error
        if isinstance(err, Conflict):
            log.critical("409 Conflict — another instance polling same token. Stopping gracefully.")
            _save_history()
            asyncio.get_running_loop().call_soon(lambda: asyncio.ensure_future(_stop_app(app)))
            return
        elif isinstance(err, RetryAfter):
            log.warning("Rate limited for %ds", err.retry_after)
        elif isinstance(err, (NetworkError, TimedOut)):
            log.warning("Network error (will retry): %s", err)
        else:
            log.error("Unhandled error: %s", err, exc_info=err)

    app.add_error_handler(error_handler)

    async def _supervised_worker():
        """Restart queue worker on crash."""
        while True:
            try:
                await _queue_worker()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.critical("Queue worker crashed: %s — restarting in 3s", exc, exc_info=True)
                await asyncio.sleep(3)

    async def start_background(app: Application):
        global heartbeat_task, worker_task
        heartbeat_task = asyncio.create_task(heartbeat_loop())
        worker_task = asyncio.create_task(_supervised_worker())

    app.post_init = start_background

    log.info("Starting polling...")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()
