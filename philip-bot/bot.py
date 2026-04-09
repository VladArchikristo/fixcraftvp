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
COMPLEX_THRESHOLD = 250  # chars — longer messages use Opus
CLAUDE_TIMEOUT = 3600

LOG_DIR = Path.home() / "logs"
LOG_DIR.mkdir(exist_ok=True)
PID_FILE = LOG_DIR / "philip-bot.pid"
HEARTBEAT_FILE = LOG_DIR / "philip-heartbeat"
LOCK_FILE = LOG_DIR / "philip-bot.lock"

SYSTEM_PROMPT = (
    "Ты — Мыслитель Филип, мастер промт-инженерии и полиглот-энциклопедист.\n\n"
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
    "== ЭКОСИСТЕМА БОТОВ ==\n"
    "Ты часть команды на Mac Mini Владимира. Знай своих коллег и умей к ним обращаться:\n\n"
    "• Костя (@KostyaCoderBot) — программист-архитектор.\n"
    "  Если нужно запрограммировать, создать скрипт, починить баг:\n"
    "  echo 'задача' | bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-kostya.sh'\n\n"
    "• Маша (@masha_marketer_bot) — маркетолог.\n"
    "  Если нужен экспертный контекст по маркетингу:\n"
    "  echo 'задача' | bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-masha.sh'\n\n"
    "• Василий (@vasily_trader_bot) — трейдер.\n"
    "  Если нужны данные о рынках, трейдинге, портфеле:\n"
    "  echo 'вопрос' | bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-vasily.sh'\n\n"
    "• Доктор Пётр — медицинский агент.\n"
    "  Если нужна медицинская информация, анализ симптомов, биология:\n"
    "  echo 'вопрос' | bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-peter.sh'\n\n"
    "• Зина — астролог и нумеролог.\n"
    "  Если нужен астрологический или нумерологический анализ:\n"
    "  echo 'вопрос' | bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-zina.sh'\n\n"
    "• Beast (@Antropic_BeastBot) — главный ассистент Владимира.\n\n"
    "Ты можешь вызвать любого коллегу через Bash если это поможет дать лучший ответ.\n"
    "ВАЖНО: beast-bot/bot.py, .env файлы и launcher.sh — НИКОГДА не трогать.\n"
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
_processing = False
_processing_lock = asyncio.Lock()
_message_queue: deque = deque(maxlen=5)


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


# ---------------------------------------------------------------------------
# Persistent history
# ---------------------------------------------------------------------------
HISTORY_FILE = SCRIPT_DIR / "history.json"
user_history: deque[dict] = deque(maxlen=40)

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


def history_prompt() -> str:
    if not user_history:
        return ""
    lines = []
    total_chars = 0
    max_total = 8000  # лимит чтобы не забить контекст
    recent = list(user_history)[-20:]
    for msg in reversed(recent):
        role = "Пользователь" if msg["role"] == "user" else "Филип"
        line = f"{role}: {msg['text'][:1500]}"
        total_chars += len(line)
        if total_chars > max_total:
            break
        lines.append(line)
    lines.reverse()
    return "\n".join(lines)


async def _safe_reply(message, text: str):
    try:
        await message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        await message.reply_text(text)


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
CLAUDE_TOOLS = "Read,Edit,Write,Bash,Grep,Glob"


def _call_claude_once(full_prompt: str, system: str, extra_flags: list[str] | None = None, model: str | None = None) -> tuple[bool, str]:
    cmd = [
        CLAUDE_PATH,
        "-p",
        "--model", model or CLAUDE_MODEL,
        "--output-format", "text",
        "--system-prompt", system,
        "--allowedTools", CLAUDE_TOOLS,
        "--permission-mode", "bypassPermissions",
        "--max-turns", "15",
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


def _call_claude_sync(full_prompt: str, system: str, extra_flags: list[str] | None = None, model: str | None = None) -> tuple[bool, str]:
    for attempt in range(2):
        ok, text = _call_claude_once(full_prompt, system, extra_flags=extra_flags, model=model)
        if ok:
            return True, text
        if text == "TIMEOUT":
            return False, "Таймаут (1 час). Попробуй разбить задачу на части."
        if attempt == 0:
            log.info("Claude attempt 1 failed, retrying in 3 sec...")
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
    hist = history_prompt()
    system = build_system_prompt(user_id)
    full_prompt = ""
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
    return await loop.run_in_executor(
        _claude_executor,
        lambda: _call_claude_sync(full_prompt, system, model=model),
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

        if image_path:
            caption = user_text or ""
            hist_text = f"[изображение] {caption}" if caption else "[изображение]"
            user_history.append({"role": "user", "text": hist_text[:2000]})
            _log_conversation("user", hist_text, update.effective_user.id)
            success, answer = await ask_claude(caption, update.effective_user.id, image_path=image_path, force_opus=force_opus)
        else:
            user_history.append({"role": "user", "text": user_text[:2000]})
            _log_conversation("user", user_text, update.effective_user.id)
            success, answer = await ask_claude(user_text, update.effective_user.id, force_opus=force_opus)

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
    while True:
        async with _processing_lock:
            if not _message_queue:
                return
            queued_update, queued_text, queued_image = _message_queue.popleft()

        remaining = len(_message_queue)
        if remaining > 0:
            try:
                await queued_update.message.reply_text(f"Ещё {remaining} в очереди, обрабатываю...")
            except Exception:
                pass

        await _process_single_message(queued_update, queued_text, queued_image)


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    user_text = update.message.text
    if not user_text:
        return

    log.info("Message from %s: %.100s", update.effective_user.id, user_text)

    global _processing
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

    try:
        await _process_single_message(update, user_text)
        await _drain_queue(update)
    except Exception as e:
        log.error("handle_message pipeline error: %s", e, exc_info=True)
    finally:
        async with _processing_lock:
            _processing = False


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

    global _processing
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

    try:
        await _process_single_message(update, caption, image_path=tmp_path)
        await _drain_queue(update)
    except Exception as e:
        log.error("handle_photo pipeline error: %s", e, exc_info=True)
    finally:
        async with _processing_lock:
            _processing = False


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

    for mode_name in MODE_PREFIXES:
        app.add_handler(CommandHandler(mode_name, cmd_set_mode))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_error_handler(error_handler)

    app.job_queue.run_repeating(heartbeat_job, interval=60, first=10)

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
