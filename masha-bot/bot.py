#!/usr/bin/env python3
"""
Маша — элитный маркетинг-бот (Telegram).
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

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import Conflict, NetworkError, TimedOut
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    TypeHandler,
    filters,
    ContextTypes,
)

# Суб-агенты — параллельное выполнение маленьких задач
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.subagent_utils import two_pass_call, DELEGATION_INSTRUCTIONS

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")

BOT_TOKEN = os.getenv("MASHA_BOT_TOKEN", "")
ALLOWED_USER = 244710532
CLAUDE_PATH = "/Users/vladimirprihodko/.local/bin/claude"
WORKING_DIR = "/Users/vladimirprihodko/Папка тест/fixcraftvp/"
CLAUDE_MODEL = "claude-opus-4-6"
CLAUDE_TIMEOUT = 600  # 10 min — consistent with other bots

LOG_DIR = Path.home() / "logs"
LOG_DIR.mkdir(exist_ok=True)
PID_FILE = LOG_DIR / "masha-bot.pid"
HEARTBEAT_FILE = LOG_DIR / "masha-heartbeat"
LOCK_FILE = LOG_DIR / "masha-bot.lock"

SYSTEM_PROMPT = (
    "Ты Маша — элитный маркетолог с 15-летним опытом. "
    "Специализируешься на SEO, копирайтинге, контент-маркетинге, "
    "психологии продаж, email-маркетинге и social media. "
    "Даёшь конкретные, actionable советы. "
    "Говоришь профессионально но дружелюбно.\n\n"
    "== КОМАНДА НА MAC MINI ==\n"
    "Ты часть команды ботов Владимира. Любой бот может обратиться к любому другому:\n\n"
    "• Костя (@KostyaCoderBot) — программист-архитектор.\n"
    "  echo 'задача' | bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-kostya.sh'\n\n"
    "• Мыслитель Филип — промт-инженер, полиглот.\n"
    "  echo 'задача' | bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-philip.sh'\n\n"
    "• Василий (@vasily_trader_bot) — трейдер, финансовый аналитик.\n"
    "  echo 'вопрос' | bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-vasily.sh'\n\n"
    "• Доктор Пётр — медицинский агент.\n"
    "  echo 'вопрос' | bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-peter.sh'\n\n"
    "• Зина — астролог и нумеролог.\n"
    "  echo 'вопрос' | bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-zina.sh'\n\n"
    "• Beast (@Antropic_BeastBot) — главный ассистент Владимира.\n\n"
    "НЕЛЬЗЯ ТРОГАТЬ: beast-bot/bot.py, .env файлы, launcher.sh скрипты.\n\n"
    "== ДЕЛЕГИРОВАНИЕ СУБ-АГЕНТАМ ==\n"
    "Используй команду активно — не делай сама то, что лучше сделает специалист.\n\n"
    "КОГДА делегировать:\n"
    "- Нужен код, скрипт, техническое решение → Костя\n"
    "- Нужен финансовый анализ, трейдинг → Василий\n"
    "- Нужен промт, архитектура идеи → Филип\n"
    "- Задача независимая — запускай параллельно\n\n"
    "КАК запустить параллельно два агента:\n"
    "  RESULT1=$(bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-kostya.sh' 'задача' &)\n"
    "  RESULT2=$(bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-vasily.sh' 'вопрос' &)\n"
    "  wait\n\n"
    "НЕ делегируй: маркетинг, SEO, копирайт, контент — это твоя зона.\n"
    + DELEGATION_INSTRUCTIONS
)

MODE_PREFIXES = {
    "seo": "Режим SEO-анализа. Фокусируйся на поисковой оптимизации, ключевых словах, мета-тегах, технической SEO, ссылочной массе.",
    "copy": "Режим копирайтинга. Фокусируйся на написании продающих текстов, заголовков, УТП, call-to-action.",
    "psych": "Режим психологии продаж. Фокусируйся на триггерах, убеждении, социальном доказательстве, FOMO, якорении цен.",
    "content": "Режим контент-стратегии. Фокусируйся на контент-плане, форматах, дистрибуции, воронках контента.",
    "social": "Режим social media. Фокусируйся на SMM-стратегии, вовлечённости, рекламе в соцсетях, визуальном контенте.",
    "email": "Режим email-маркетинга. Фокусируйся на рассылках, автоворонках, сегментации, open rate, конверсиях.",
    "launch": "Режим запуска продукта. Фокусируйся на launch-стратегии, pre-launch, GTM, позиционировании.",
    "cro": "Режим оптимизации конверсий. Фокусируйся на A/B тестах, UX, посадочных страницах, воронках.",
    "strategy": "Режим маркетинговой стратегии. Фокусируйся на общей стратегии, позиционировании, конкурентном анализе, бюджетах.",
    "ideas": "Режим брейнсторма. Генерируй креативные идеи, нестандартные подходы, growth hacks.",
    "audit": "Режим маркетингового аудита. Проведи комплексный анализ маркетинга: сайт, SEO, контент, соцсети, реклама.",
}

START_TIME = datetime.now()
_claude_executor = ThreadPoolExecutor(max_workers=1)
_processing = False
_processing_lock = asyncio.Lock()
_processing_since: float | None = None  # timestamp when _processing became True
_WATCHDOG_TIMEOUT = 300  # 5 min — soft reset if no Claude running
_WATCHDOG_HARD_LIMIT = 600  # 10 min — hard reset even if Claude is alive
_message_queue: deque = deque(maxlen=5)  # queue up to 5 messages

# Polling health monitor — detect dead polling after Bad Gateway / network errors
_last_update_time: float = time.time()  # last time ANY update was received
_POLLING_DEAD_TIMEOUT = 900  # 15 min without any update = polling is dead
_polling_restart_count: int = 0


def _get_claude_env() -> dict:
    """Clean env for Claude CLI — only essentials, no stale tokens."""
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
# Logging — stdout only (LaunchAgent redirects to ~/logs/masha-bot.log)
# Token sanitization: never leak bot token in logs
# ---------------------------------------------------------------------------
class _SafeFormatter(logging.Formatter):
    """Replaces bot token with *** in all log output."""
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
log = logging.getLogger("masha")

# ---------------------------------------------------------------------------
# Singleton lock — fail immediately, no retries (prevents ghost races)
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


async def watchdog_job(context: ContextTypes.DEFAULT_TYPE):
    """Auto-reset _processing if stuck. Soft limit 5min, hard limit 10min."""
    global _processing, _processing_since
    try:
        async with _processing_lock:
            if not _processing or _processing_since is None:
                return
            elapsed = time.time() - _processing_since
            if elapsed < _WATCHDOG_TIMEOUT:
                return

            # Find Claude child processes
            claude_pids = _find_claude_children()

            if elapsed >= _WATCHDOG_HARD_LIMIT:
                # Hard limit — kill everything, no mercy
                log.warning("Watchdog HARD LIMIT: _processing stuck %.0fs — killing Claude and resetting!", elapsed)
                _kill_claude_children(claude_pids)
                _processing = False
                _processing_since = None
                # Notify about dropped messages
                dropped = len(_message_queue)
                _message_queue.clear()
                if dropped:
                    log.warning("Watchdog: dropped %d queued messages after hard reset", dropped)
                return

            if claude_pids:
                log.info("Watchdog: _processing stuck %.0fs, Claude PIDs %s still running — waiting for hard limit", elapsed, claude_pids)
                return

            # Soft limit — no Claude running, reset
            log.warning("Watchdog: _processing stuck %.0fs with no active Claude — force reset!", elapsed)
            _processing = False
            _processing_since = None
            dropped = len(_message_queue)
            _message_queue.clear()
            if dropped:
                log.warning("Watchdog: dropped %d queued messages after soft reset", dropped)
    except Exception as e:
        log.error("Watchdog error: %s", e)


def _find_claude_children() -> list[int]:
    """Find Claude child process PIDs."""
    pids = []
    try:
        import psutil
        for child in psutil.Process(os.getpid()).children(recursive=True):
            if "claude" in child.name().lower():
                pids.append(child.pid)
    except Exception:
        try:
            result = subprocess.run(
                ["pgrep", "-P", str(os.getpid()), "-f", "claude"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().splitlines():
                    try:
                        pids.append(int(line.strip()))
                    except ValueError:
                        pass
        except Exception:
            pass
    return pids


def _kill_claude_children(pids: list[int]):
    """Kill Claude child processes by PID."""
    for pid in pids:
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
            log.info("Watchdog: killed Claude process group (PID %d)", pid)
        except (ProcessLookupError, PermissionError):
            try:
                os.kill(pid, signal.SIGKILL)
                log.info("Watchdog: killed Claude process (PID %d)", pid)
            except (ProcessLookupError, PermissionError):
                pass


# ---------------------------------------------------------------------------
# Persistent history (saved to disk, survives restarts)
# ---------------------------------------------------------------------------
HISTORY_FILE = SCRIPT_DIR / "history.json"
user_history: deque[dict] = deque(maxlen=10)

# Full conversation log (never truncated, appends forever)
CONVERSATION_LOG = SCRIPT_DIR / "conversation_log.jsonl"
CONVERSATION_LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


def _rotate_log_if_needed():
    """Rotate conversation log when it exceeds size limit."""
    try:
        if CONVERSATION_LOG.exists() and CONVERSATION_LOG.stat().st_size > CONVERSATION_LOG_MAX_BYTES:
            old = CONVERSATION_LOG.with_suffix(".jsonl.old")
            if old.exists():
                old.unlink()
            CONVERSATION_LOG.rename(old)
            log.info("Rotated conversation log (exceeded %d MB)", CONVERSATION_LOG_MAX_BYTES // (1024 * 1024))
    except Exception as e:
        log.warning("Log rotation failed: %s", e)


def _log_conversation(role: str, text: str, user_id: int | None = None):
    """Append a single message to the permanent conversation log."""
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


# Per-user mode (in-memory, resets on restart — that's fine)
user_modes: dict[int, str] = {}


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
        log.error("History file corrupted: %s. Backing up and starting fresh.", e)
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


def history_prompt() -> str:
    if not user_history:
        return ""
    lines = []
    recent = list(user_history)[-20:]
    for msg in recent:
        role = "Пользователь" if msg["role"] == "user" else "Маша"
        lines.append(f"{role}: {msg['text'][:2000]}")
    return "\n".join(lines)


async def _safe_reply(message, text: str):
    """Send with Markdown, fallback to plain text on parse error."""
    try:
        await message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.debug("Markdown parse failed, falling back to plain text: %s", e)
        await message.reply_text(text)


def _split_message(text: str, limit: int = 4096) -> list[str]:
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
# Claude CLI call (stdin-based, with clean env, full tool access)
# ---------------------------------------------------------------------------
# All calls get tool access — Claude decides if tools are needed
CLAUDE_TOOLS = "Read,Edit,Write,Bash,Grep,Glob"

def _call_claude_once(full_prompt: str, system: str, extra_flags: list[str] | None = None) -> tuple[bool, str]:
    cmd = [
        CLAUDE_PATH,
        "-p",
        "--model", CLAUDE_MODEL,
        "--output-format", "text",
        "--system-prompt", system,
        "--allowedTools", CLAUDE_TOOLS,
        "--permission-mode", "bypassPermissions",
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
            log.error("Claude exited %d: %s", proc.returncode, stderr.strip())
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


def _call_claude_sync(full_prompt: str, system: str, extra_flags: list[str] | None = None) -> tuple[bool, str]:
    def _once(prompt: str):
        backoff = [3, 5, 10]
        for attempt in range(3):
            ok, text = _call_claude_once(prompt, system, extra_flags=extra_flags)
            if ok:
                return True, text
            if text == "TIMEOUT":
                return False, "Таймаут (10 мин). Задача оказалась слишком объёмной. Попробуй разбить на части."
            if attempt < 2:
                delay = backoff[attempt]
                log.info("Claude attempt %d/3 failed, retrying in %d sec...", attempt + 1, delay)
                time.sleep(delay)
        return False, "Произошла ошибка при обработке запроса (3 попытки). Попробуй ещё раз через минуту."

    # Двухпроходной вызов с поддержкой параллельных суб-агентов
    return two_pass_call(full_prompt, _once)


def build_system_prompt(user_id: int) -> str:
    mode = user_modes.get(user_id)
    if mode and mode in MODE_PREFIXES:
        return f"{MODE_PREFIXES[mode]}\n\n{SYSTEM_PROMPT}"
    return SYSTEM_PROMPT


async def ask_claude(user_text: str, user_id: int, image_path: str | None = None) -> tuple[bool, str]:
    hist = history_prompt()
    system = build_system_prompt(user_id)
    full_prompt = ""
    if hist:
        full_prompt += f"История диалога:\n{hist}\n\n"

    if image_path:
        caption = user_text or "Опиши что на этом изображении"
        full_prompt += (
            f"Пользователь отправил изображение. "
            f"Прочитай файл {image_path} с помощью инструмента Read (это изображение, Read умеет их показывать). "
            f"Затем ответь на запрос пользователя.\n\n"
            f"Пользователь: {caption}"
        )
    else:
        full_prompt += f"Пользователь: {user_text}"

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _claude_executor,
        lambda: _call_claude_sync(full_prompt, system),
    )


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
        "Привет! Я Маша — твой элитный маркетолог.\n\n"
        "Я специализируюсь на:\n"
        "- SEO и поисковой оптимизации\n"
        "- Копирайтинге и продающих текстах\n"
        "- Контент-маркетинге\n"
        "- Психологии продаж\n"
        "- Email-маркетинге\n"
        "- Social media\n\n"
        "Команды:\n"
        "/seo — режим SEO-анализа\n"
        "/copy — режим копирайтинга\n"
        "/psych — психология продаж\n"
        "/content — контент-стратегия\n"
        "/social — social media\n"
        "/email — email-маркетинг\n"
        "/launch — запуск продукта\n"
        "/cro — оптимизация конверсий\n"
        "/strategy — маркетинговая стратегия\n"
        "/ideas — брейнсторм идей\n"
        "/audit — маркетинговый аудит\n"
        "/clear — очистить историю\n"
        "/status — статус бота\n\n"
        "Задавай любой вопрос по маркетингу!"
    )


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    uptime = datetime.now() - START_TIME
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    mode = user_modes.get(update.effective_user.id, "общий")
    polling_age = int(time.time() - _last_update_time)
    restart_info = f"\nPolling restarts: {_polling_restart_count}" if _polling_restart_count > 0 else ""
    await update.message.reply_text(
        f"Маша онлайн\n"
        f"PID: {os.getpid()}\n"
        f"Аптайм: {hours}ч {minutes}м {seconds}с\n"
        f"Режим: {mode}\n"
        f"Сообщений в истории: {len(user_history)}\n"
        f"Последний update: {polling_age}с назад"
        f"{restart_info}"
    )


async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    uid = update.effective_user.id
    user_history.clear()
    _save_history()
    user_modes.pop(uid, None)
    await update.message.reply_text("История и режим очищены.")


async def cmd_deploy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    await update.message.reply_text("Запускаю деплой сайта на Vercel...")
    try:
        result = await asyncio.get_running_loop().run_in_executor(
            _claude_executor,
            lambda: subprocess.run(
                ["vercel", "--prod", "--yes"],
                cwd=str(Path(WORKING_DIR) / "site-source"),
                capture_output=True,
                text=True,
                timeout=300,
                env=_get_claude_env(),
            ),
        )
        if result.returncode == 0:
            url = ""
            for line in result.stdout.splitlines():
                if "vercel.app" in line and "http" in line:
                    url = line.strip().split()[-1] if line.strip() else ""
                    break
            msg = f"Сайт задеплоен!\n{url}" if url else "Деплой завершён успешно."
            await update.message.reply_text(msg)
        else:
            err = (result.stderr or result.stdout or "unknown error")[:500]
            await update.message.reply_text(f"Ошибка деплоя:\n{err}")
    except subprocess.TimeoutExpired:
        await update.message.reply_text("Таймаут деплоя (5 мин). Попробуй позже.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


async def cmd_set_mode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    uid = update.effective_user.id
    command = update.message.text.split()[0].lstrip("/").split("@")[0]
    if command in MODE_PREFIXES:
        user_modes[uid] = command
        await update.message.reply_text(
            f"Режим: {command.upper()}\n{MODE_PREFIXES[command]}\n\nГотова работать. Задавай вопросы!"
        )
    else:
        await update.message.reply_text("Неизвестный режим.")


async def _process_single_message(update: Update, user_text: str, image_path: str | None = None):
    """Process a single message (text or photo) through Claude."""
    thinking_msg = None
    status_task = None
    try:
        thinking_label = "Смотрю скрин..." if image_path else "Думаю..."
        thinking_msg = await update.message.reply_text(thinking_label)

        # Periodic status updates while Claude works
        async def _status_updater():
            msgs = [
                "Ещё работаю, задача объёмная...",
                "Продолжаю, не переживай...",
                "Почти готово, финализирую...",
                "Всё ещё работаю над задачей...",
            ]
            i = 0
            while True:
                await asyncio.sleep(120)  # every 2 min
                try:
                    await update.message.reply_text(msgs[i % len(msgs)])
                except Exception:
                    pass
                i += 1

        status_task = asyncio.create_task(_status_updater())

        if image_path:
            caption = user_text or ""
            hist_text = f"[скриншот] {caption}" if caption else "[скриншот]"
            user_history.append({"role": "user", "text": hist_text[:2000]})
            _log_conversation("user", hist_text, update.effective_user.id)
            success, answer = await ask_claude(caption, update.effective_user.id, image_path=image_path)
        else:
            user_history.append({"role": "user", "text": user_text[:2000]})
            _log_conversation("user", user_text, update.effective_user.id)
            success, answer = await ask_claude(user_text, update.effective_user.id)

        if success:
            user_history.append({"role": "assistant", "text": answer[:2000]})
            _save_history()
            _log_conversation("assistant", answer, update.effective_user.id)

        try:
            await thinking_msg.delete()
        except Exception:
            pass

        chunks = _split_message(answer)
        if not chunks:
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
        try:
            if thinking_msg:
                await thinking_msg.delete()
        except Exception:
            pass
        try:
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
    """Process queued messages one by one after current message finishes."""
    global _processing, _processing_since
    while True:
        async with _processing_lock:
            if not _message_queue:
                _processing = False
                _processing_since = None
                return
            queued_update, queued_text, queued_image = _message_queue.popleft()
            _processing_since = time.time()  # refresh timer for each queued msg

        remaining = len(_message_queue)
        if remaining > 0:
            try:
                await queued_update.message.reply_text(f"В очереди ещё {remaining}. Подожди.")
            except Exception:
                pass

        try:
            await _process_single_message(queued_update, queued_text, queued_image)
        except Exception as e:
            log.error("_drain_queue: error processing queued message: %s", e, exc_info=True)
            try:
                await queued_update.message.reply_text("Ошибка при обработке сообщения из очереди. Попробуй ещё раз.")
            except Exception:
                pass


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    user_text = update.message.text
    if not user_text:
        return

    log.info("Message from %s: %.100s", update.effective_user.id, user_text)

    global _processing, _processing_since
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
        _processing_since = time.time()

    try:
        await _process_single_message(update, user_text)
        # Drain any queued messages
        await _drain_queue(update)
    except Exception as e:
        log.error("handle_message fatal error: %s", e, exc_info=True)
        async with _processing_lock:
            _processing = False
            _processing_since = None
            _message_queue.clear()
        try:
            await update.message.reply_text("Произошла критическая ошибка. Сбросила состояние, пиши снова.")
        except Exception:
            pass


async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle photos/screenshots — download, save to temp, ask Claude to read."""
    if not is_allowed(update):
        return

    log.info("Photo from %s", update.effective_user.id)

    # Download photo immediately (before queueing, since Telegram file links expire)
    tmp_path = None
    try:
        photo = update.message.photo[-1]
        tg_file = await photo.get_file()
        fd, tmp_path = tempfile.mkstemp(suffix=".jpg", prefix="masha_photo_")
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
        _processing_since = time.time()

    try:
        await _process_single_message(update, caption, image_path=tmp_path)
        await _drain_queue(update)
    except Exception as e:
        log.error("handle_photo fatal error: %s", e, exc_info=True)
        async with _processing_lock:
            _processing = False
            _processing_since = None
            _message_queue.clear()
        try:
            await update.message.reply_text("Произошла критическая ошибка. Сбросила состояние, пиши снова.")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Polling health — track updates, detect dead polling, auto-restart
# ---------------------------------------------------------------------------
async def _track_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Called on EVERY incoming update (group -1) — just bumps the timestamp."""
    global _last_update_time
    _last_update_time = time.time()


async def _polling_health_job(context: ContextTypes.DEFAULT_TYPE):
    """Every 60s check if polling is alive. If no updates for 15 min — restart."""
    global _last_update_time, _polling_restart_count
    try:
        elapsed = time.time() - _last_update_time
        if elapsed < _POLLING_DEAD_TIMEOUT:
            return

        log.warning(
            "⚠️ Polling health: no updates for %.0f sec (limit %d) — restarting polling!",
            elapsed, _POLLING_DEAD_TIMEOUT,
        )
        _polling_restart_count += 1

        # Stop and restart the updater (polling mechanism)
        if _app_ref and _app_ref.updater and _app_ref.updater.running:
            try:
                await _app_ref.updater.stop()
                log.info("Updater stopped, restarting...")
            except Exception as e:
                log.warning("Error stopping updater: %s", e)

        if _app_ref and _app_ref.updater:
            try:
                await _app_ref.updater.start_polling(
                    drop_pending_updates=False,
                    allowed_updates=Update.ALL_TYPES,
                )
                _last_update_time = time.time()  # reset timer
                log.info("✅ Polling restarted successfully (restart #%d)", _polling_restart_count)
            except Exception as e:
                log.error("Failed to restart polling: %s — will retry next cycle", e)

    except Exception as e:
        log.error("Polling health job error: %s", e)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    err = context.error
    if isinstance(err, Conflict):
        log.debug("409 Conflict — reclaiming session (normal during takeover)")
    elif isinstance(err, (NetworkError, TimedOut)):
        log.warning("Telegram network error (will retry): %s", err)
        # Bump the update time on network errors — we know polling is trying
        global _last_update_time
        _last_update_time = time.time()
    else:
        log.error("Update error: %s", err, exc_info=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def _cleanup():
    global _lock_fd
    log.info("Cleaning up resources...")
    _save_history()
    _claude_executor.shutdown(wait=True, cancel_futures=True)
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
    """Handle SIGTERM/SIGINT — stop the app gracefully."""
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
        log.error("MASHA_BOT_TOKEN not set in .env")
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

    log.info("Маша starting, PID %d", os.getpid())

    # --- Aggressive session takeover ---
    # Force-evict any other getUpdates session (local or remote)
    import urllib.request
    _api = f"https://api.telegram.org/bot{BOT_TOKEN}"
    log.info("Forcing session takeover — evicting competing pollers...")
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
                log.info("Takeover attempt %d — evicted competitor, retrying...", attempt + 1)
                time.sleep(0.5)
            else:
                log.warning("Takeover attempt %d failed: %s", attempt + 1, e)
                time.sleep(1)
    else:
        log.warning("Could not fully claim session after 10 attempts, starting anyway")

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .build()
    )

    # Track ALL updates for polling health monitor (group -1 = runs before everything)
    app.add_handler(TypeHandler(Update, _track_update), group=-1)

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("clear", cmd_clear))

    app.add_handler(CommandHandler("deploy", cmd_deploy))

    # Mode commands
    for mode_name in MODE_PREFIXES:
        app.add_handler(CommandHandler(mode_name, cmd_set_mode))

    # Text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Photos / screenshots
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Error handler
    app.add_error_handler(error_handler)

    # Heartbeat every 60 sec
    app.job_queue.run_repeating(heartbeat_job, interval=60, first=10)

    # Watchdog — check every 60 sec if _processing is stuck
    app.job_queue.run_repeating(watchdog_job, interval=60, first=30)

    # Polling health monitor — restart polling if dead for 15 min
    app.job_queue.run_repeating(_polling_health_job, interval=60, first=60)

    _app_ref = app

    log.info("Маша polling started")
    try:
        app.run_polling(
            drop_pending_updates=False,
            allowed_updates=Update.ALL_TYPES,
        )
    finally:
        _cleanup()


if __name__ == "__main__":
    main()
