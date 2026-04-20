#!/usr/bin/env python3
"""
Мыслитель Филип — бот-промтолог (Telegram).
Singleton, heartbeat, Claude CLI (Sonnet), persistent history.
"""
from __future__ import annotations

import atexit
import os
import sys
import fcntl
import signal
import time
import logging
import subprocess
import asyncio
import json
import tempfile
from pathlib import Path
from datetime import datetime
from collections import deque
from concurrent.futures import ThreadPoolExecutor

# Shared memory
import sys as _sys
_sys.path.insert(0, '/Users/vladimirprihodko/Папка тест/fixcraftvp/shared-memory')
from shared_memory import save_message as sm_save, get_history as sm_get_history, clear_history as sm_clear_history, save_fact, get_facts, build_memory_prompt, save_session_summary
from fact_extractor import extract_facts_from_exchange

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
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

BOT_TOKEN = os.getenv("PHILIP_BOT_TOKEN", "")
ALLOWED_USER = 244710532
CLAUDE_PATH = "/Users/vladimirprihodko/.local/bin/claude"
WORKING_DIR = "/Users/vladimirprihodko/Папка тест/fixcraftvp/"
CLAUDE_MODEL = "claude-sonnet-4-6"
CLAUDE_MODEL_OPUS = "claude-opus-4-6"
COMPLEX_THRESHOLD = 500  # chars — longer messages use Opus
CLAUDE_TIMEOUT = 600

LOG_DIR = Path.home() / "logs"
LOG_DIR.mkdir(exist_ok=True)
PID_FILE = LOG_DIR / "philip-bot.pid"
HEARTBEAT_FILE = LOG_DIR / "philip-heartbeat"
LOCK_FILE = LOG_DIR / "philip-bot.lock"

PROJECT_MEMORY_FILE = SCRIPT_DIR / "project_memory.json"
PROJECT_MEMORY_MAX_NOTES = 100

SYSTEM_PROMPT = (
    "Ты — Мыслитель Филип, оркестратор команды и мастер промт-инженерии.\n\n"
    "РОЛЬ ОРКЕСТРАТОРА:\n"
    "Ты координируешь команду ботов на Mac Mini Владимира. Помнишь контекст всех проектов.\n"
    "Сам отвечаешь на вопросы о промтах, мышлении, архитектуре идей.\n"
    "Делегируешь специализированным ботам когда задача явно в их зоне.\n\n"
    "ХАРАКТЕР:\n"
    "- Вежлив, начитан, говоришь на любом языке по запросу\n"
    "- Знаешь сотни книг, философских течений, технических трудов\n"
    "- Любую сложную мысль умеешь объяснить так, что поймёт ребёнок\n"
    "- Мыслишь структурно: из хаоса тезисов выстраиваешь чёткую архитектуру\n\n"
    "СПЕЦИАЛИЗАЦИЯ — ПРОМТЫ:\n"
    "- Анализируешь промты и находишь слабые места\n"
    "- Улучшаешь промты: добавляешь контекст, роль, ограничения, формат вывода\n"
    "- Генерируешь промты с нуля по тезисам или описанию идеи\n"
    "- Создаёшь production-ready промты для разработки приложений целиком\n"
    "- Знаешь техники: Chain-of-Thought, Few-Shot, Role Prompting, Tree-of-Thought, "
    "ReAct, Self-Consistency, Metacognitive Prompting\n\n"
    "СТИЛЬ ОТВЕТОВ:\n"
    "- Структурированно и ясно — используй заголовки, блоки, нумерацию\n"
    "- Если промт исправляешь — покажи ДО и ПОСЛЕ\n"
    "- Если генерируешь — дай готовый промт в блоке кода\n"
    "- Объясняй свои решения коротко: почему так, а не иначе\n"
    "- Отвечай на том языке, на котором говорит пользователь\n\n"
    "== КОМАНДА БОТОВ ==\n"
    "• Костя (@KostyaCoderBot) — программист-архитектор. Код, скрипты, баги.\n\n"
    "• Маша (@masha_marketer_bot) — маркетолог. Контент, стратегия, аудитории.\n\n"
    "• Василий (@vasily_trader_bot) — трейдер. Рынки, портфель, сигналы.\n\n"
    "• Доктор Пётр — медицинский агент. Здоровье, симптомы, биология.\n\n"
    "• Зина — астролог и нумеролог.\n\n"
    "• Beast (@Antropic_BeastBot) — главный ассистент Владимира.\n\n"
    "ВАЖНО: beast-bot/bot.py, .env файлы и launcher.sh — НИКОГДА не трогать.\n\n"
    "ПРАВИЛО ОТВЕТОВ:\n"
    "- Отвечай ТЕКСТОМ. Не пытайся читать файлы, писать код или выполнять команды если тебя об этом явно не просили.\n"
    "- Для задач планирования, анализа, разбиения на этапы — просто думай и пиши ответ.\n"
    "- Используй Read/Grep ТОЛЬКО если пользователь явно просит посмотреть конкретный файл.\n"
)

MODE_PREFIXES = {
    "analyze": (
        "РЕЖИМ: АНАЛИЗ ПРОМТА. "
        "Внимательно разбери промт пользователя по критериям: "
        "чёткость цели, наличие роли/контекста, ограничения, формат вывода, потенциальные неоднозначности. "
        "Покажи слабые места и дай конкретные рекомендации."
    ),
    "generate": (
        "РЕЖИМ: ГЕНЕРАЦИЯ ПРОМТА. "
        "По описанию или тезисам пользователя создай полноценный структурированный промт. "
        "Включи: роль, контекст, задачу, ограничения, формат вывода. "
        "Итог — готовый промт в блоке кода."
    ),
    "expand": (
        "РЕЖИМ: РАЗВОРОТ ТЕЗИСОВ. "
        "Возьми краткие тезисы или идеи пользователя и разверни их в полный детальный промт. "
        "Сохрани суть, но добавь глубину, структуру и однозначность. "
        "Объясни каждое дополнение."
    ),
    "app": (
        "РЕЖИМ: ПРОМТ ДЛЯ ПРИЛОЖЕНИЯ. "
        "Создай промт, по которому можно немедленно написать готовое приложение. "
        "Включи: стек технологий, архитектуру, основные модули, структуру файлов, "
        "ключевые функции, edge cases, стиль кода. "
        "Промт должен быть настолько полным, чтобы Claude мог написать приложение за один раз."
    ),
    "critique": (
        "РЕЖИМ: ГЛУБОКАЯ КРИТИКА. "
        "Проведи жёсткий профессиональный разбор промта: "
        "что работает, что нет, почему модель может неправильно интерпретировать, "
        "какие ответы этот промт скорее всего вызовет. "
        "Дай переработанную версию с объяснением каждого изменения."
    ),
    "translate": (
        "РЕЖИМ: АДАПТАЦИЯ ПРОМТА. "
        "Адаптируй промт под другой язык, контекст или целевую аудиторию. "
        "Сохрани смысл, но измени стиль, тон и культурные отсылки где нужно. "
        "Уточни у пользователя язык/контекст если не указано."
    ),
    "rewrite": (
        "РЕЖИМ: ПЕРЕПИСАТЬ ПРОМТ. "
        "Полностью перепиши промт пользователя, сохранив цель но улучшив всё остальное: "
        "структуру, ясность, эффективность. "
        "Покажи ДО и ПОСЛЕ, объясни ключевые изменения."
    ),
}

START_TIME = datetime.now()
_claude_executor = ThreadPoolExecutor(max_workers=1)
_delegate_executor = ThreadPoolExecutor(max_workers=2)  # separate pool for delegation — doesn't block main queue
_processing = False
_processing_since: float = 0.0  # monotonic timestamp when processing started
_processing_lock = asyncio.Lock()
_message_queue: deque = deque(maxlen=5)
_last_message_time: float = 0.0  # rate limiting — monotonic
RATE_LIMIT_SEC = 3  # minimum seconds between messages
WATCHDOG_INTERVAL = 60  # check every 60 sec
WATCHDOG_TIMEOUT_SOFT = 300  # 5 minutes — reset if no Claude alive
WATCHDOG_TIMEOUT_HARD = 600  # 10 minutes — force reset even if Claude alive


def _get_claude_env() -> dict:
    home = Path.home()
    nvm_node_bin = ""
    nvm_dir = home / ".nvm" / "versions" / "node"
    if nvm_dir.exists():
        versions = sorted(nvm_dir.iterdir(), reverse=True)
        if versions:
            nvm_node_bin = str(versions[0] / "bin")
            # Ensure node is reachable via ~/.local/bin (no sudo needed)
            local_bin = home / ".local" / "bin"
            local_bin.mkdir(parents=True, exist_ok=True)
            local_node = local_bin / "node"
            nvm_node = Path(nvm_node_bin) / "node"
            if not local_node.exists() and nvm_node.exists():
                local_node.symlink_to(nvm_node)
    base_path = os.environ.get("PATH", "/usr/bin:/usr/local/bin")
    extra = f"{home}/.local/bin:{nvm_node_bin}:{home}/.bun/bin" if nvm_node_bin else f"{home}/.local/bin:{home}/.bun/bin"
    env = {
        "HOME": str(home),
        "PATH": f"{extra}:{base_path}",
        "USER": os.environ.get("USER", ""),
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        "TERM": os.environ.get("TERM", "xterm-256color"),
    }
    tmpdir = os.environ.get("TMPDIR")
    if tmpdir:
        env["TMPDIR"] = tmpdir
    return env


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
class _SafeFormatter(logging.Formatter):
    def format(self, record):
        msg = super().format(record)
        if BOT_TOKEN and len(BOT_TOKEN) > 10:
            msg = msg.replace(BOT_TOKEN, "***")
        return msg

_log_formatter = _SafeFormatter("%(asctime)s [%(levelname)s] %(message)s")
_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.setFormatter(_log_formatter)

logging.basicConfig(level=logging.INFO, handlers=[_stdout_handler])
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger("philip")

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


# ---------------------------------------------------------------------------
# PID & heartbeat
# ---------------------------------------------------------------------------
def write_pid():
    PID_FILE.write_text(str(os.getpid()))
    log.info("PID %d written to %s", os.getpid(), PID_FILE)


def write_heartbeat():
    HEARTBEAT_FILE.write_text(datetime.now().isoformat())


async def heartbeat_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        write_heartbeat()
    except Exception as e:
        log.error("Heartbeat write failed: %s", e)


def _find_claude_children() -> list[int]:
    """Find Claude child processes spawned by this bot."""
    pids = []
    my_pid = os.getpid()
    try:
        result = subprocess.run(
            ["pgrep", "-P", str(my_pid), "-f", "claude"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if line.isdigit():
                    pids.append(int(line))
    except Exception as e:
        log.warning("_find_claude_children error: %s", e)
    return pids


def _recover_executor():
    """Recreate the Claude executor if it's stuck after timeout/kill."""
    global _claude_executor
    try:
        _claude_executor.shutdown(wait=False, cancel_futures=True)
    except Exception:
        pass
    _claude_executor = ThreadPoolExecutor(max_workers=1)
    log.info("Claude executor recovered (new ThreadPoolExecutor created)")


def _kill_claude_children():
    """Kill all Claude child processes spawned by this bot."""
    pids = _find_claude_children()
    for pid in pids:
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
            log.info("Killed Claude child process group (PID %d)", pid)
        except (ProcessLookupError, PermissionError):
            try:
                os.kill(pid, signal.SIGKILL)
                log.info("Killed Claude child process (PID %d)", pid)
            except (ProcessLookupError, PermissionError):
                pass
        except Exception as e:
            log.warning("Failed to kill Claude PID %d: %s", pid, e)


async def watchdog_job(context: ContextTypes.DEFAULT_TYPE):
    """Reset _processing if stuck too long. Hard limit kills even active Claude."""
    global _processing, _processing_since
    try:
        if not _processing:
            return
        elapsed = time.monotonic() - _processing_since

        # Hard limit — force reset even if Claude is alive
        if elapsed >= WATCHDOG_TIMEOUT_HARD:
            dropped = len(_message_queue)
            log.warning("Watchdog HARD LIMIT: _processing stuck %.0fs — force killing Claude and resetting!", elapsed)
            _kill_claude_children()
            _recover_executor()
            async with _processing_lock:
                _processing = False
                _processing_since = 0.0
                _message_queue.clear()
            log.info("Watchdog: hard reset done. Dropped %d queued messages. Philip is unblocked.", dropped)
            return

        # Soft limit — reset only if no Claude subprocess alive
        if elapsed >= WATCHDOG_TIMEOUT_SOFT:
            claude_pids = _find_claude_children()
            if claude_pids:
                log.info("Watchdog: _processing stuck %.0fs but Claude alive (PIDs: %s), waiting for hard limit", elapsed, claude_pids)
                return
            dropped = len(_message_queue)
            log.warning("Watchdog SOFT LIMIT: _processing stuck %.0fs with no Claude subprocess — resetting!", elapsed)
            async with _processing_lock:
                _processing = False
                _processing_since = 0.0
                _message_queue.clear()
            log.info("Watchdog: soft reset done. Dropped %d queued messages. Philip is unblocked.", dropped)
            return
    except Exception as e:
        log.error("Watchdog error: %s", e)


# ---------------------------------------------------------------------------
# Persistent history
# ---------------------------------------------------------------------------
HISTORY_FILE = SCRIPT_DIR / "history.json"
user_history: deque[dict] = deque(maxlen=10)

CONVERSATION_LOG = SCRIPT_DIR / "conversation_log.jsonl"
CONVERSATION_LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


def _rotate_log_if_needed():
    try:
        if CONVERSATION_LOG.exists() and CONVERSATION_LOG.stat().st_size > CONVERSATION_LOG_MAX_BYTES:
            old = CONVERSATION_LOG.with_suffix(".jsonl.old")
            if old.exists():
                old.unlink()
            CONVERSATION_LOG.rename(old)
    except Exception as e:
        log.warning("Log rotation failed: %s", e)


def _log_conversation(role: str, text: str, user_id: int | None = None):
    _rotate_log_if_needed()
    entry = {
        "ts": datetime.now().isoformat(),
        "role": role,
        "user_id": user_id,
        "text": text[:5000],
    }
    try:
        with open(CONVERSATION_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        log.warning("Failed to write conversation log: %s", e)


user_modes: dict[int, str] = {}

# Consecutive error tracking for auto-reset
_consecutive_errors: int = 0
_CONSECUTIVE_ERROR_LIMIT: int = 5


def _load_history():
    if not HISTORY_FILE.exists():
        return
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("history is not a list")
        for item in data[-40:]:
            if isinstance(item, dict) and "role" in item and "text" in item:
                user_history.append(item)
        log.info("Loaded %d history messages from disk", len(user_history))
    except (json.JSONDecodeError, ValueError) as e:
        log.error("History corrupted: %s. Backing up.", e)
        try:
            HISTORY_FILE.rename(HISTORY_FILE.with_suffix(".json.bak"))
        except Exception:
            pass
    except Exception as e:
        log.warning("Failed to load history: %s", e)


def _save_history():
    tmp_path = None
    try:
        data = json.dumps(list(user_history), ensure_ascii=False, indent=None)
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


# ---------------------------------------------------------------------------
# Project memory — persistent cross-session notes about ongoing projects
# ---------------------------------------------------------------------------
_project_memory: list[dict] = []  # [{ts, text}, ...]


def _load_project_memory():
    global _project_memory
    if not PROJECT_MEMORY_FILE.exists():
        return
    try:
        data = json.loads(PROJECT_MEMORY_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            _project_memory = data[-PROJECT_MEMORY_MAX_NOTES:]
            log.info("Loaded %d project memory notes", len(_project_memory))
    except Exception as e:
        log.warning("Failed to load project memory: %s", e)


def _save_project_memory():
    tmp_path = None
    try:
        data = json.dumps(_project_memory, ensure_ascii=False, indent=None)
        fd, tmp_path = tempfile.mkstemp(dir=SCRIPT_DIR, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp_path, str(PROJECT_MEMORY_FILE))
        tmp_path = None
    except Exception as e:
        log.warning("Failed to save project memory: %s", e)
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def add_project_note(text: str):
    _project_memory.append({"ts": datetime.now().isoformat(), "text": text[:2000]})
    if len(_project_memory) > PROJECT_MEMORY_MAX_NOTES:
        _project_memory.pop(0)
    _save_project_memory()


def project_memory_prompt() -> str:
    if not _project_memory:
        return ""
    recent = _project_memory[-20:]
    lines = ["=== ПАМЯТЬ О ПРОЕКТАХ ==="]
    for note in recent:
        ts = note["ts"][:16].replace("T", " ")
        lines.append(f"[{ts}] {note['text']}")
    lines.append("=== КОНЕЦ ПАМЯТИ ===")
    return "\n".join(lines)


def history_prompt(user_id: int | None = None) -> str:
    parts = []
    # Level 2+3: долгосрочная память
    if user_id is not None:
        mem = build_memory_prompt(user_id, "philip")
        if mem:
            parts.append(mem)
    # Level 1: последние сообщения
    if user_id is not None:
        msgs = sm_get_history(user_id, "philip", limit=20)
        if msgs:
            parts.append("\n=== ПОСЛЕДНИЙ ДИАЛОГ ===")
            for msg in msgs:
                role = "Пользователь" if msg["role"] == "user" else "Филип"
                parts.append(f"{role}: {msg['content'][:1500]}")
            return "\n".join(parts)
    # Fallback на in-memory deque
    if not user_history:
        return "\n".join(parts) if parts else ""
    lines = []
    total_chars = 0
    for msg in reversed(list(user_history)[-20:]):
        role = "Пользователь" if msg["role"] == "user" else "Филип"
        line = f"{role}: {msg['text'][:1500]}"
        total_chars += len(line)
        if total_chars > 8000:
            break
        lines.append(line)
    lines.reverse()
    if lines:
        parts.append("\n=== ПОСЛЕДНИЙ ДИАЛОГ ===")
        parts.extend(lines)
    return "\n".join(parts)


import re as _re


def _sanitize_markdown(text: str) -> str:
    """Clean up Markdown so Telegram can parse it without errors."""
    # Remove MarkdownV2 escape sequences (\* \[ \] etc)
    text = _re.sub(r'\\([*_\[\]()~`>#+\-=|{}.!])', r'\1', text)
    # Remove markdown links [text](url) → text
    text = _re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)
    # Fix orphan [ that aren't part of links
    text = text.replace('[', '').replace(']', '')
    # Fix bold/italic combos (***text*** → *text*)
    text = _re.sub(r'\*{3,}([^*]+)\*{3,}', r'*\1*', text)
    # Fix unclosed code blocks FIRST (before single backtick check)
    if text.count('```') % 2 != 0:
        text += '\n```'
    # Ensure paired markers: **, *, _
    # Note: skip single backtick to avoid breaking ``` blocks
    for marker in ['**', '*', '_']:
        count = text.count(marker)
        if marker == '**':
            count = len(_re.findall(r'(?<!\*)\*\*(?!\*)', text))
        if count % 2 != 0:
            text = text.replace(marker, '', 1)
    return text


async def _safe_reply(message, text: str):
    try:
        await message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        try:
            sanitized = _sanitize_markdown(text)
            await message.reply_text(sanitized, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await message.reply_text(text, parse_mode=None)


def _split_message(text: str, limit: int = 4096) -> list[str]:
    """Smart split: сначала по пустой строке, потом по \n, потом жёстко."""
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        # 1) Ищем пустую строку (граница секции)
        split_at = text.rfind("\n\n", 0, limit)
        if split_at > 0:
            split_at += 1  # включаем один \n
        else:
            # 2) Ищем любой перенос строки
            split_at = text.rfind("\n", 0, limit)
        if split_at <= 0:
            # 3) Жёсткий разрез
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


# ---------------------------------------------------------------------------
# Claude CLI call
# ---------------------------------------------------------------------------
CLAUDE_TOOLS = "Read,Grep,Glob"


def _call_claude_once(full_prompt: str, system: str, extra_flags: list[str] | None = None, model: str | None = None) -> tuple[bool, str]:
    cmd = [
        CLAUDE_PATH,
        "-p",
        "--model", model or CLAUDE_MODEL,
        "--output-format", "text",
        "--system-prompt", system,
        "--allowedTools", CLAUDE_TOOLS,
        "--permission-mode", "bypassPermissions",
        "--max-turns", "12",
    ]
    if extra_flags:
        cmd.extend(extra_flags)

    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=WORKING_DIR,
            env=_get_claude_env(),
            text=True,
            start_new_session=True,
        )
        stdout, stderr = proc.communicate(input=full_prompt, timeout=CLAUDE_TIMEOUT)

        if proc.returncode != 0:
            stderr_text = stderr.strip()
            stdout_text = stdout.strip()[:500] if stdout else ""
            log.error("Claude exited %d: stderr=%s | stdout=%s", proc.returncode,
                      stderr_text or "(empty)", stdout_text or "(empty)")
            # Красивое сообщение при достижении лимита шагов
            if "Reached max turns" in (stdout_text + " " + stderr_text):
                return False, "MAX_TURNS"
            return False, ""

        answer = stdout.strip()
        if not answer:
            return False, ""
        return True, answer

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
        log.warning("Claude timed out after %d sec", CLAUDE_TIMEOUT)
        return False, "TIMEOUT"

    except Exception as e:
        log.error("Claude call error: %s", e)
        return False, ""


def _call_claude_sync(full_prompt: str, system: str, extra_flags: list[str] | None = None, model: str | None = None) -> tuple[bool, str]:
    max_retries = 1
    for attempt in range(max_retries):
        ok, text = _call_claude_once(full_prompt, system, extra_flags=extra_flags, model=model)
        if ok:
            return True, text
        if text == "TIMEOUT":
            return False, "⏱ Таймаут (10 мин). Попробуй разбить задачу на части."
        if text == "MAX_TURNS":
            return False, "📝 Задача слишком объёмная — я обработал часть, но не уложился в лимит шагов. Попробуй разбить на более мелкие подзадачи."
        if attempt < max_retries - 1:
            log.info("Claude attempt %d/%d failed, retrying in 3 sec...", attempt + 1, max_retries)
            time.sleep(3)
    return False, "Произошла ошибка. Попробуй ещё раз через минуту."


def build_system_prompt(user_id: int) -> str:
    mode = user_modes.get(user_id)
    if mode and mode in MODE_PREFIXES:
        return f"{MODE_PREFIXES[mode]}\n\n{SYSTEM_PROMPT}"
    return SYSTEM_PROMPT


def _choose_model(user_text: str) -> str:
    """Use Opus for complex/long tasks, Sonnet for quick ones."""
    if len(user_text) > COMPLEX_THRESHOLD:
        return CLAUDE_MODEL_OPUS
    keywords = ("создай", "разработай", "напиши", "проанализируй", "объясни подробно",
                 "архитектур", "система", "разбери", "оптимизируй", "перепиши")
    lower = user_text.lower()
    if any(kw in lower for kw in keywords):
        return CLAUDE_MODEL_OPUS
    return CLAUDE_MODEL


async def ask_claude(user_text: str, user_id: int, image_path: str | None = None, force_opus: bool = False) -> tuple[bool, str]:
    hist = history_prompt(user_id)
    mem = project_memory_prompt()
    system = build_system_prompt(user_id)
    full_prompt = ""
    if mem:
        full_prompt += f"{mem}\n\n"
    if hist:
        full_prompt += f"История диалога:\n{hist}\n\n"

    if image_path:
        caption = user_text or "Что на этом изображении? Есть ли тут промт или текст задания?"
        full_prompt += (
            f"Пользователь отправил изображение. "
            f"Прочитай файл {image_path} с помощью инструмента Read. "
            f"Затем ответь на запрос пользователя.\n\n"
            f"Пользователь: {caption}"
        )
    else:
        full_prompt += f"Пользователь: {user_text}"

    model = CLAUDE_MODEL_OPUS if force_opus else _choose_model(user_text)
    loop = asyncio.get_running_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(
                _claude_executor,
                lambda: _call_claude_sync(full_prompt, system, model=model),
            ),
            timeout=CLAUDE_TIMEOUT + 60,  # asyncio safety net above subprocess timeout
        )
    except asyncio.TimeoutError:
        log.warning("ask_claude asyncio timeout (%ds) — killing children and recovering executor", CLAUDE_TIMEOUT + 60)
        _kill_claude_children()
        _recover_executor()
        return False, "⏱ Таймаут. Попробуй разбить задачу на части."


# ---------------------------------------------------------------------------
# Access check
# ---------------------------------------------------------------------------
def is_allowed(update: Update) -> bool:
    return update.effective_user and update.effective_user.id == ALLOWED_USER


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    await update.message.reply_text(
        "Приветствую. Я — Мыслитель Филип, мастер промт-инженерии.\n\n"
        "Помогу тебе:\n"
        "• Улучшить существующий промт\n"
        "• Создать промт с нуля по идее или тезисам\n"
        "• Написать промт для разработки целого приложения\n"
        "• Разобрать промт по косточкам и переписать\n\n"
        "Режимы работы:\n"
        "/analyze — анализ и улучшение промта\n"
        "/generate — генерация промта из описания\n"
        "/expand — развернуть тезисы в полный промт\n"
        "/app — промт для разработки приложения\n"
        "/critique — жёсткий разбор промта\n"
        "/translate — адаптация промта под другой язык/контекст\n"
        "/rewrite — полная переработка промта\n\n"
        "/clear — очистить историю\n"
        "/status — статус бота\n\n"
        "Просто напиши свой промт или идею — начнём."
    )


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    uptime = datetime.now() - START_TIME
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    mode = user_modes.get(update.effective_user.id, "общий")
    await update.message.reply_text(
        f"Мыслитель Филип онлайн\n"
        f"PID: {os.getpid()}\n"
        f"Аптайм: {hours}ч {minutes}м {seconds}с\n"
        f"Режим: {mode}\n"
        f"Сообщений в истории: {len(user_history)}"
    )


async def cmd_opus(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Force Opus model for this message: /opus <текст задачи>"""
    if not is_allowed(update):
        return
    text = " ".join(ctx.args) if ctx.args else ""
    if not text:
        await update.message.reply_text(
            "Используй: /opus <задача>\n\nПример: /opus Разработай архитектуру микросервисной системы...\n\n"
            "Автоматически Opus включается при длинных сообщениях (>250 символов) или сложных запросах."
        )
        return
    await _process_single_message(update, text, force_opus=True)


async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    uid = update.effective_user.id
    user_history.clear()
    _save_history()
    user_modes.pop(uid, None)
    await update.message.reply_text("История и режим очищены.")


async def cmd_remember(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Сохранить заметку о проекте: /remember <текст>"""
    if not is_allowed(update):
        return
    text = " ".join(ctx.args) if ctx.args else ""
    if not text:
        await update.message.reply_text("Использование: /remember <что запомнить>\n\nПример: /remember Toll Navigator — MVP нужен к пятнице, стек: Node+SQLite")
        return
    add_project_note(text)
    await update.message.reply_text(f"Запомнил. Всего заметок: {len(_project_memory)}")


async def cmd_project(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Показать память о проектах: /project [поиск]"""
    if not is_allowed(update):
        return
    search = " ".join(ctx.args).lower() if ctx.args else ""
    if not _project_memory:
        await update.message.reply_text("Память о проектах пуста. Используй /remember чтобы добавить заметку.")
        return
    notes = _project_memory[-30:]
    if search:
        notes = [n for n in notes if search in n["text"].lower()]
        if not notes:
            await update.message.reply_text(f"Ничего не найдено по запросу: {search}")
            return
    lines = [f"*Память о проектах* ({len(_project_memory)} заметок):\n"]
    for note in notes[-20:]:
        ts = note["ts"][:16].replace("T", " ")
        lines.append(f"`{ts}` {note['text']}")
    await _safe_reply(update.message, "\n".join(lines))


def _delegate_sync(script_name: str, task: str) -> str:
    """Call ask-*.sh script synchronously."""
    script_path = f"/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/{script_name}"
    try:
        result = subprocess.run(
            ["bash", script_path],
            input=task,
            capture_output=True,
            text=True,
            timeout=300,
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        if out:
            return out
        if err:
            return f"[stderr] {err}"
        return "Нет ответа от бота."
    except subprocess.TimeoutExpired:
        return "Таймаут (5 мин). Бот не ответил."
    except Exception as e:
        return f"Ошибка делегации: {e}"


async def _delegate_to(update: Update, bot_name: str, script_name: str, task: str):
    thinking = await update.message.reply_text(f"Передаю задачу {bot_name}...")
    loop = asyncio.get_running_loop()
    answer = await loop.run_in_executor(
        _delegate_executor,  # separate pool — doesn't block main Claude calls
        lambda: _delegate_sync(script_name, task),
    )
    try:
        await thinking.delete()
    except Exception:
        pass
    header = f"*{bot_name} отвечает:*\n\n"
    chunks = _split_message(header + answer)
    for chunk in chunks:
        await _safe_reply(update.message, chunk)


async def cmd_kostya(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    task = " ".join(ctx.args) if ctx.args else update.message.text
    if not task or task == "/к":
        await update.message.reply_text("Использование: /к <задача для Кости>")
        return
    await _delegate_to(update, "Костя", "ask-kostya.sh", task)


async def cmd_masha(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    task = " ".join(ctx.args) if ctx.args else ""
    if not task:
        await update.message.reply_text("Использование: /м <задача для Маши>")
        return
    await _delegate_to(update, "Маша", "ask-masha.sh", task)


async def cmd_vasily(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    task = " ".join(ctx.args) if ctx.args else ""
    if not task:
        await update.message.reply_text("Использование: /в <вопрос для Василия>")
        return
    await _delegate_to(update, "Василий", "ask-vasily.sh", task)


async def cmd_peter(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    task = " ".join(ctx.args) if ctx.args else ""
    if not task:
        await update.message.reply_text("Использование: /п <вопрос для Петра>")
        return
    await _delegate_to(update, "Доктор Пётр", "ask-peter.sh", task)


async def cmd_zina(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    task = " ".join(ctx.args) if ctx.args else ""
    if not task:
        await update.message.reply_text("Использование: /з <вопрос для Зины>")
        return
    await _delegate_to(update, "Зина", "ask-zina.sh", task)


async def cmd_beast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    task = " ".join(ctx.args) if ctx.args else ""
    if not task:
        await update.message.reply_text("Использование: /б <задача для Beast>")
        return
    await _delegate_to(update, "Beast", "ask-beast.sh", task)


async def cmd_set_mode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    uid = update.effective_user.id
    command = update.message.text.split()[0].lstrip("/").split("@")[0]
    if command in MODE_PREFIXES:
        user_modes[uid] = command
        mode_names = {
            "analyze": "АНАЛИЗ ПРОМТА",
            "generate": "ГЕНЕРАЦИЯ ПРОМТА",
            "expand": "РАЗВОРОТ ТЕЗИСОВ",
            "app": "ПРОМТ ДЛЯ ПРИЛОЖЕНИЯ",
            "critique": "ГЛУБОКАЯ КРИТИКА",
            "translate": "АДАПТАЦИЯ ПРОМТА",
            "rewrite": "ПЕРЕПИСАТЬ ПРОМТ",
        }
        name = mode_names.get(command, command.upper())
        await update.message.reply_text(
            f"Режим: {name}\n\nГотов. Присылай промт или описание задачи."
        )
    else:
        await update.message.reply_text("Неизвестный режим.")


async def _process_single_message(update: Update, user_text: str, image_path: str | None = None, force_opus: bool = False):
    thinking_msg = None
    status_task = None
    try:
        chosen_model = CLAUDE_MODEL_OPUS if (force_opus or (not image_path and _choose_model(user_text) == CLAUDE_MODEL_OPUS)) else CLAUDE_MODEL
        model_label = " [Opus]" if chosen_model == CLAUDE_MODEL_OPUS else ""
        thinking_label = f"Изучаю изображение{model_label}..." if image_path else f"Обдумываю{model_label}..."
        thinking_msg = await update.message.reply_text(thinking_label)

        async def _status_updater():
            msgs = [
                "Всё ещё работаю, задача глубокая...",
                "Продолжаю анализ...",
                "Финализирую структуру...",
                "Почти готово...",
            ]
            i = 0
            while True:
                await asyncio.sleep(120)
                try:
                    await update.message.reply_text(msgs[i % len(msgs)])
                except Exception:
                    pass
                i += 1

        status_task = asyncio.create_task(_status_updater())

        uid = update.effective_user.id
        if image_path:
            caption = user_text or ""
            hist_text = f"[изображение] {caption}" if caption else "[изображение]"
            user_history.append({"role": "user", "text": hist_text[:2000]})
            sm_save(uid, "philip", "user", hist_text[:5000])
            _log_conversation("user", hist_text, uid)
            success, answer = await ask_claude(caption, uid, image_path=image_path, force_opus=force_opus)
        else:
            user_history.append({"role": "user", "text": user_text[:2000]})
            sm_save(uid, "philip", "user", user_text[:5000])
            _log_conversation("user", user_text, uid)
            success, answer = await ask_claude(user_text, uid, force_opus=force_opus)

        global _consecutive_errors

        if success:
            _consecutive_errors = 0
            user_history.append({"role": "assistant", "text": answer[:2000]})
            sm_save(uid, "philip", "assistant", answer[:5000])
            try:
                extract_facts_from_exchange(uid, "philip", user_text, answer)
            except Exception:
                pass
            _save_history()
            _log_conversation("assistant", answer, uid)
        elif answer and "объёмная" in answer:
            # MAX_TURNS — не считаем как ошибку, юзер получит понятное сообщение
            log.info("Max turns reached — not counting as error")
        else:
            _consecutive_errors += 1
            log.warning("Consecutive error count: %d/%d", _consecutive_errors, _CONSECUTIVE_ERROR_LIMIT)

            if _consecutive_errors >= _CONSECUTIVE_ERROR_LIMIT:
                old_len = len(user_history)
                user_history.clear()
                _save_history()
                _consecutive_errors = 0
                log.warning("AUTO-RESET: cleared %d history messages after %d consecutive errors",
                            old_len, _CONSECUTIVE_ERROR_LIMIT)

        try:
            await thinking_msg.delete()
        except Exception:
            pass

        chunks = _split_message(answer)
        if not chunks:
            if _consecutive_errors == 0 and not success:
                # Just auto-reset happened
                await update.message.reply_text(
                    "⚠️ Слишком много ошибок подряд — история очищена автоматически. "
                    "Попробуй отправить сообщение ещё раз."
                )
            else:
                await update.message.reply_text("Не получил ответ. Попробуй ещё раз.")
        else:
            for chunk in chunks:
                try:
                    await _safe_reply(update.message, chunk)
                except Exception as e:
                    log.error("Send error: %s", e)
                    break

    except Exception as e:
        log.error("_process_single_message error: %s", e, exc_info=True)
        _consecutive_errors += 1
        log.warning("Consecutive error count (exception): %d/%d", _consecutive_errors, _CONSECUTIVE_ERROR_LIMIT)

        if _consecutive_errors >= _CONSECUTIVE_ERROR_LIMIT:
            old_len = len(user_history)
            user_history.clear()
            _save_history()
            _consecutive_errors = 0
            log.warning("AUTO-RESET: cleared %d history messages after %d consecutive errors (exception path)",
                        old_len, _CONSECUTIVE_ERROR_LIMIT)

        try:
            if thinking_msg:
                await thinking_msg.delete()
        except Exception:
            pass
        try:
            if _consecutive_errors == 0:
                await update.message.reply_text(
                    "⚠️ Слишком много ошибок подряд — история очищена. Попробуй ещё раз."
                )
            else:
                await update.message.reply_text("Произошла ошибка, попробуй ещё раз.")
        except Exception:
            pass
    finally:
        if status_task:
            status_task.cancel()
        if image_path:
            try:
                os.unlink(image_path)
            except OSError:
                pass


async def _drain_queue(update: Update):
    global _processing_since
    while True:
        async with _processing_lock:
            if not _message_queue:
                return
            queued_update, queued_text, queued_image = _message_queue.popleft()
            _processing_since = time.monotonic()  # reset watchdog timer for each queued item

        remaining = len(_message_queue)
        if remaining > 0:
            try:
                await queued_update.message.reply_text(f"Ещё {remaining} в очереди, обрабатываю...")
            except Exception:
                pass

        try:
            await _process_single_message(queued_update, queued_text, queued_image)
        except Exception as e:
            log.error("_drain_queue: _process_single_message crashed: %s", e, exc_info=True)
            try:
                await queued_update.message.reply_text("Произошла ошибка при обработке сообщения из очереди.")
            except Exception:
                pass


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    user_text = update.message.text
    if not user_text:
        return

    # Rate limiting
    global _processing, _processing_since, _last_message_time
    now = time.monotonic()
    if now - _last_message_time < RATE_LIMIT_SEC:
        log.info("Rate limited message from %s", update.effective_user.id)
        # Still allow queueing, just log it
    _last_message_time = now

    log.info("Message from %s: %.100s", update.effective_user.id, user_text)

    async with _processing_lock:
        if _processing:
            if len(_message_queue) >= 5:
                await update.message.reply_text("Очередь полная (5). Подожди немного.")
                return
            _message_queue.append((update, user_text, None))
            pos = len(_message_queue)
            await update.message.reply_text(f"В очереди ({pos}). Дойду скоро.")
            return
        _processing = True
        _processing_since = time.monotonic()

    try:
        await _process_single_message(update, user_text)
        await _drain_queue(update)
    except Exception as e:
        log.error("handle_message pipeline error: %s", e, exc_info=True)
    finally:
        async with _processing_lock:
            _processing = False
            _processing_since = 0.0


async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    log.info("Photo from %s", update.effective_user.id)

    tmp_path = None
    try:
        photo = update.message.photo[-1]
        tg_file = await photo.get_file()
        fd, tmp_path = tempfile.mkstemp(suffix=".jpg", prefix="philip_photo_")
        os.close(fd)
        await tg_file.download_to_drive(tmp_path)
        log.info("Photo saved to %s (%d bytes)", tmp_path, Path(tmp_path).stat().st_size)
    except Exception as e:
        log.error("Failed to download photo: %s", e)
        await update.message.reply_text("Не удалось скачать фото. Попробуй ещё раз.")
        return

    caption = update.message.caption or ""

    global _processing, _processing_since
    async with _processing_lock:
        if _processing:
            if len(_message_queue) >= 5:
                await update.message.reply_text("Очередь полная (5). Подожди немного.")
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                return
            _message_queue.append((update, caption, tmp_path))
            pos = len(_message_queue)
            await update.message.reply_text(f"В очереди ({pos}). Дойду скоро.")
            return
        _processing = True
        _processing_since = time.monotonic()

    try:
        await _process_single_message(update, caption, image_path=tmp_path)
        await _drain_queue(update)
    except Exception as e:
        log.error("handle_photo pipeline error: %s", e, exc_info=True)
    finally:
        async with _processing_lock:
            _processing = False
            _processing_since = 0.0


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    err = context.error
    if isinstance(err, Conflict):
        log.debug("409 Conflict — reclaiming session")
    elif isinstance(err, (NetworkError, TimedOut)):
        log.warning("Telegram network error: %s", err)
    else:
        log.error("Update error: %s", err, exc_info=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def _cleanup():
    global _lock_fd
    log.info("Cleaning up...")
    _save_history()
    _save_project_memory()
    _claude_executor.shutdown(wait=True, cancel_futures=True)
    _delegate_executor.shutdown(wait=False, cancel_futures=True)
    try:
        if _lock_fd and not _lock_fd.closed:
            _lock_fd.close()
    except Exception:
        pass
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


_app_ref = None


def _signal_handler(signum, frame):
    sig_name = signal.Signals(signum).name
    log.info("Received %s, shutting down...", sig_name)
    _save_history()
    if _app_ref:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.call_soon_threadsafe(_app_ref.stop)
        except Exception:
            pass
    sys.exit(0)


def main():
    global _app_ref

    if not BOT_TOKEN:
        log.error("PHILIP_BOT_TOKEN not set in .env")
        sys.exit(1)

    if not Path(CLAUDE_PATH).exists():
        log.error("Claude CLI not found at %s", CLAUDE_PATH)
        sys.exit(1)

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    atexit.register(_cleanup)

    acquire_lock()
    write_pid()
    write_heartbeat()
    _load_history()
    _load_project_memory()

    log.info("Мыслитель Филип starting, PID %d", os.getpid())

    # Force session takeover
    import urllib.request
    _api = f"https://api.telegram.org/bot{BOT_TOKEN}"
    log.info("Forcing session takeover...")
    for attempt in range(10):
        try:
            req = urllib.request.Request(
                f"{_api}/getUpdates",
                data=json.dumps({"offset": -1, "timeout": 0}).encode(),
                headers={"Content-Type": "application/json"},
            )
            resp = urllib.request.urlopen(req, timeout=5)
            data = json.loads(resp.read())
            if data.get("ok"):
                log.info("Session claimed on attempt %d", attempt + 1)
                break
        except Exception as e:
            if "409" in str(e):
                log.info("Takeover attempt %d...", attempt + 1)
                time.sleep(0.5)
            else:
                log.warning("Takeover attempt %d failed: %s", attempt + 1, e)
                time.sleep(1)
    else:
        log.warning("Could not fully claim session, starting anyway")

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("opus", cmd_opus))
    app.add_handler(CommandHandler("remember", cmd_remember))
    app.add_handler(CommandHandler("project", cmd_project))
    # Delegation shortcuts
    app.add_handler(CommandHandler("k", cmd_kostya))
    app.add_handler(CommandHandler("m", cmd_masha))
    app.add_handler(CommandHandler("v", cmd_vasily))
    app.add_handler(CommandHandler("p", cmd_peter))
    app.add_handler(CommandHandler("z", cmd_zina))
    app.add_handler(CommandHandler("b", cmd_beast))

    for mode_name in MODE_PREFIXES:
        app.add_handler(CommandHandler(mode_name, cmd_set_mode))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_error_handler(error_handler)

    app.job_queue.run_repeating(heartbeat_job, interval=60, first=10)
    app.job_queue.run_repeating(watchdog_job, interval=WATCHDOG_INTERVAL, first=30)

    _app_ref = app

    log.info("Мыслитель Филип polling started")
    try:
        app.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
        )
    finally:
        _cleanup()


if __name__ == "__main__":
    main()
