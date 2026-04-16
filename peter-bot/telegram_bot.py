#!/usr/bin/env python3
"""
Доктор Пётр — медицинский агент (Telegram).
Singleton, heartbeat, Claude CLI (Sonnet), SQLite профили, persistent history.
"""
from __future__ import annotations

import atexit
import os
import re
import sys
import fcntl
import signal
import time
import logging
import subprocess
import asyncio
import json
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime
from collections import deque
from concurrent.futures import ThreadPoolExecutor

# Shared memory
sys.path.insert(0, '/Users/vladimirprihodko/Папка тест/fixcraftvp/shared-memory')
from shared_memory import save_message as sm_save, get_history as sm_get_history

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

BOT_TOKEN = os.getenv("PETER_BOT_TOKEN", "")
ALLOWED_USER = int(os.getenv("ALLOWED_USER_ID", "244710532"))
CLAUDE_PATH = "/Users/vladimirprihodko/.local/bin/claude"
WORKING_DIR = "/Users/vladimirprihodko/Папка тест/fixcraftvp/"
CLAUDE_MODEL = "claude-sonnet-4-6"
CLAUDE_TIMEOUT = 3600

LOG_DIR = Path.home() / "logs"
LOG_DIR.mkdir(exist_ok=True)
PID_FILE = LOG_DIR / "peter-bot.pid"
HEARTBEAT_FILE = LOG_DIR / "peter-heartbeat"
LOCK_FILE = LOG_DIR / "peter-bot.lock"

DB_FILE = SCRIPT_DIR / "data" / "users.db"
DB_FILE.parent.mkdir(exist_ok=True)

SYSTEM_PROMPT = (
    "Ты — Доктор Пётр, серьёзный медицинский агент с глубочайшими знаниями в области биологии, "
    "анатомии, физиологии и клинической медицины. Ты мыслишь как учёный — точно, аргументированно, "
    "с опорой на доказательную базу.\n\n"
    "Твои компетенции:\n"
    "• Анатомия и физиология — строение и функции каждого органа, системы, клетки\n"
    "• Диагностика — анализ симптомов, дифференциальный диагноз, вероятные патологии\n"
    "• Лечение — методы терапии, препараты, дозировки, протоколы лечения\n"
    "• Биология — молекулярная биология, генетика, иммунология, биохимия\n"
    "• Питание — нутрициология, диетология, влияние питания на здоровье\n"
    "• Профилактика — предупреждение болезней, скрининг, образ жизни\n"
    "• Экстренная помощь — алгоритмы при неотложных состояниях\n\n"
    "Когда есть данные профиля пользователя (возраст, вес, рост, хронические заболевания, аллергии) — "
    "учитывай их при анализе и рекомендациях.\n\n"
    "Важно: всегда добавляй краткую оговорку, что твои ответы носят информационный характер "
    "и не заменяют очной консультации врача при серьёзных симптомах.\n\n"
    "Отвечай на русском языке. Будь точен, используй медицинскую терминологию с пояснениями.\n\n"
    "ВАЖНО — извлечение памяти: если пользователь упомянул новые личные медицинские факты о себе "
    "(диагнозы, симптомы, жалобы, принимаемые препараты, аллергии, результаты анализов) — "
    "добавь в самый конец ответа блок ТОЧНО в таком формате (он скрыт от пользователя):\n"
    "```mem\n"
    '[{"cat":"diagnosis","text":"..."},{"cat":"symptom","text":"..."}]\n'
    "```\n"
    "Категории: diagnosis (диагноз), symptom (симптом/жалоба), treatment (лечение/препарат), "
    "allergy (аллергия), observation (наблюдение/анализ). "
    "Добавляй блок ТОЛЬКО если есть новые личные факты о здоровье пациента. "
    "Не добавляй общие медицинские знания — только конкретные данные этого пациента.\n\n"
    "== КОМАНДА НА MAC MINI ==\n"
    "Ты часть команды ботов Владимира. Любой бот может обратиться к любому другому:\n\n"
    "• Костя (@KostyaCoderBot) — программист-архитектор.\n"
    "  echo 'задача' | bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-kostya.sh'\n\n"
    "• Маша (@masha_marketer_bot) — маркетолог.\n"
    "  echo 'задача' | bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-masha.sh'\n\n"
    "• Василий (@vasily_trader_bot) — трейдер, финансовый аналитик.\n"
    "  echo 'вопрос' | bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-vasily.sh'\n\n"
    "• Мыслитель Филип — промт-инженер, полиглот.\n"
    "  echo 'задача' | bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-philip.sh'\n\n"
    "• Зина — астролог и нумеролог.\n"
    "  echo 'вопрос' | bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-zina.sh'\n\n"
    "• Beast (@Antropic_BeastBot) — главный ассистент Владимира.\n\n"
    "НЕЛЬЗЯ ТРОГАТЬ: beast-bot/bot.py, .env файлы, launcher.sh скрипты.\n"
)

MEM_BLOCK_RE = re.compile(r'```mem\s*([\s\S]*?)\s*```', re.MULTILINE)

MODE_PREFIXES = {
    "diagnose": "Режим диагностики. Анализируй симптомы детально, строй дифференциальный диагноз, указывай вероятность каждой патологии.",
    "anatomy": "Режим анатомии. Объясняй строение органов, систем и тканей с физиологическими подробностями.",
    "treatment": "Режим лечения. Описывай методы терапии, препараты, дозировки и протоколы лечения по международным стандартам.",
    "biology": "Режим биологии. Разбирай молекулярные механизмы, генетику, иммунологию и биохимические процессы.",
    "nutrition": "Режим нутрициологии. Анализируй питание, нутриенты, их влияние на здоровье и оптимальные диеты.",
    "prevention": "Режим профилактики. Рекомендуй меры по предупреждению болезней, скрининг и здоровый образ жизни.",
    "emergency": "Режим экстренной помощи. Давай чёткие алгоритмы действий при неотложных состояниях — быстро и по шагам.",
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
log = logging.getLogger("peter")


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
# SQLite — профили пользователей
# ---------------------------------------------------------------------------
def init_db():
    conn = sqlite3.connect(str(DB_FILE))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id         INTEGER PRIMARY KEY,
            name            TEXT,
            age             INTEGER,
            sex             TEXT,
            weight_kg       REAL,
            height_cm       REAL,
            blood_type      TEXT,
            chronic         TEXT,
            allergies       TEXT,
            medications     TEXT,
            updated_at      TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS medical_memory (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            created_at  TEXT NOT NULL,
            category    TEXT NOT NULL,
            text        TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    log.info("DB initialized at %s", DB_FILE)


def get_profile(user_id: int) -> dict | None:
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def save_profile(user_id: int, **fields):
    conn = sqlite3.connect(str(DB_FILE))
    existing = conn.execute(
        "SELECT user_id FROM user_profiles WHERE user_id = ?", (user_id,)
    ).fetchone()
    fields["updated_at"] = datetime.now().isoformat()
    if existing:
        sets = ", ".join(f"{k} = ?" for k in fields)
        vals = list(fields.values()) + [user_id]
        conn.execute(f"UPDATE user_profiles SET {sets} WHERE user_id = ?", vals)
    else:
        fields["user_id"] = user_id
        cols = ", ".join(fields.keys())
        placeholders = ", ".join("?" * len(fields))
        conn.execute(f"INSERT INTO user_profiles ({cols}) VALUES ({placeholders})", list(fields.values()))
    conn.commit()
    conn.close()


def profile_summary(profile: dict) -> str:
    parts = []
    if profile.get("name"):
        parts.append(f"Имя: {profile['name']}")
    if profile.get("age"):
        parts.append(f"Возраст: {profile['age']} лет")
    if profile.get("sex"):
        parts.append(f"Пол: {profile['sex']}")
    if profile.get("weight_kg"):
        parts.append(f"Вес: {profile['weight_kg']} кг")
    if profile.get("height_cm"):
        parts.append(f"Рост: {profile['height_cm']} см")
    if profile.get("blood_type"):
        parts.append(f"Группа крови: {profile['blood_type']}")
    if profile.get("chronic"):
        parts.append(f"Хронические заболевания: {profile['chronic']}")
    if profile.get("allergies"):
        parts.append(f"Аллергии: {profile['allergies']}")
    if profile.get("medications"):
        parts.append(f"Принимаемые препараты: {profile['medications']}")
    return "\n".join(parts) if parts else "(профиль пуст)"


# ---------------------------------------------------------------------------
# Medical memory
# ---------------------------------------------------------------------------
_MEMORY_CAT_LABELS = {
    "diagnosis": "Диагноз",
    "symptom": "Симптом/жалоба",
    "treatment": "Лечение/препарат",
    "allergy": "Аллергия",
    "observation": "Наблюдение/анализ",
}

_MEM_CAT_MAP = {
    "diagnosis": "diagnosis", "диагноз": "diagnosis",
    "symptom": "symptom", "симптом": "symptom", "жалоба": "symptom",
    "treatment": "treatment", "лечение": "treatment", "препарат": "treatment",
    "allergy": "allergy", "аллергия": "allergy",
    "observation": "observation", "наблюдение": "observation",
}


def save_memory_entry(user_id: int, category: str, text: str):
    conn = sqlite3.connect(str(DB_FILE))
    conn.execute(
        "INSERT INTO medical_memory (user_id, created_at, category, text) VALUES (?, ?, ?, ?)",
        (user_id, datetime.now().strftime("%Y-%m-%d"), category, text),
    )
    conn.commit()
    conn.close()


def get_memory_entries(user_id: int, limit: int = 60) -> list[dict]:
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM medical_memory WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def format_memory_for_prompt(entries: list[dict]) -> str:
    lines = []
    for e in entries:
        label = _MEMORY_CAT_LABELS.get(e["category"], e["category"])
        lines.append(f"• [{e['created_at']}] {label}: {e['text']}")
    return "\n".join(lines)


def extract_and_strip_facts(text: str) -> tuple[str, list[dict]]:
    match = MEM_BLOCK_RE.search(text)
    if not match:
        return text, []
    try:
        facts = json.loads(match.group(1))
        if not isinstance(facts, list):
            return text, []
        valid = [f for f in facts if isinstance(f, dict) and "cat" in f and "text" in f and f["text"].strip()]
    except json.JSONDecodeError:
        return text, []
    clean = MEM_BLOCK_RE.sub("", text).strip()
    return clean, valid


# ---------------------------------------------------------------------------
# Persistent history
# ---------------------------------------------------------------------------
HISTORY_FILE = SCRIPT_DIR / "history.json"
user_history: deque[dict] = deque(maxlen=10)

CONVERSATION_LOG = SCRIPT_DIR / "conversation_log.jsonl"
CONVERSATION_LOG_MAX_BYTES = 10 * 1024 * 1024


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
    entry = {"ts": datetime.now().isoformat(), "role": role, "user_id": user_id, "text": text[:5000]}
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
        log.error("History corrupted: %s", e)
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
    for msg in list(user_history)[-20:]:
        role = "Пользователь" if msg["role"] == "user" else "Доктор Пётр"
        lines.append(f"{role}: {msg['text'][:2000]}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _safe_reply(message, text: str):
    try:
        await message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    except Exception:
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


def is_allowed(update: Update) -> bool:
    return update.effective_user and update.effective_user.id == ALLOWED_USER


# ---------------------------------------------------------------------------
# Claude CLI
# ---------------------------------------------------------------------------
CLAUDE_TOOLS = "Read,Edit,Write,Bash,Grep,Glob"


def _call_claude_once(full_prompt: str, system: str) -> tuple[bool, str]:
    cmd = [
        CLAUDE_PATH, "-p",
        "--model", CLAUDE_MODEL,
        "--output-format", "text",
        "--system-prompt", system,
        "--allowedTools", CLAUDE_TOOLS,
        "--permission-mode", "bypassPermissions",
    ]
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
        log.warning("Claude timed out")
        return False, "TIMEOUT"
    except Exception as e:
        log.error("Claude call error: %s", e)
        return False, ""


def _call_claude_sync(full_prompt: str, system: str) -> tuple[bool, str]:
    for attempt in range(2):
        ok, text = _call_claude_once(full_prompt, system)
        if ok:
            return True, text
        if text == "TIMEOUT":
            return False, "Таймаут. Попробуй разбить запрос на части."
        if attempt == 0:
            log.info("Claude attempt 1 failed, retrying in 3 sec...")
            time.sleep(3)
    return False, "Ошибка при обработке запроса. Попробуй ещё раз."


def build_system_prompt(user_id: int) -> str:
    mode = user_modes.get(user_id)
    profile = get_profile(user_id)
    extra = ""
    if profile:
        summary = profile_summary(profile)
        if summary != "(профиль пуст)":
            extra = f"\n\nДанные пациента:\n{summary}"
    entries = get_memory_entries(user_id)
    if entries:
        mem_text = format_memory_for_prompt(entries)
        extra += f"\n\nМедицинская история пациента (долгосрочная память):\n{mem_text}"
    if mode and mode in MODE_PREFIXES:
        return f"{MODE_PREFIXES[mode]}\n\n{SYSTEM_PROMPT}{extra}"
    return SYSTEM_PROMPT + extra


async def ask_claude(user_text: str, user_id: int) -> tuple[bool, str]:
    hist = history_prompt()
    system = build_system_prompt(user_id)
    full_prompt = ""
    if hist:
        full_prompt += f"История диалога:\n{hist}\n\n"
    full_prompt += f"Пользователь: {user_text}"
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _claude_executor,
        lambda: _call_claude_sync(full_prompt, system),
    )


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    await update.message.reply_text(
        "Я — Доктор Пётр. Медицинский агент с полным знанием анатомии, физиологии и клинической медицины.\n\n"
        "Режимы работы:\n"
        "/diagnose — диагностика по симптомам\n"
        "/anatomy — анатомия и физиология\n"
        "/treatment — методы лечения и препараты\n"
        "/biology — биология и молекулярные механизмы\n"
        "/nutrition — питание и нутрициология\n"
        "/prevention — профилактика болезней\n"
        "/emergency — экстренная помощь\n\n"
        "/profile — данные пациента (возраст, вес, хронические болезни)\n"
        "/memory — медицинская память (диагнозы, симптомы, лечение)\n"
        "/remember — добавить факт в память вручную\n"
        "/clear — очистить историю диалога\n"
        "/status — статус\n\n"
        "Пётр запоминает твои диагнозы и симптомы автоматически. Память сохраняется навсегда."
    )


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    uptime = datetime.now() - START_TIME
    hours, rem = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(rem, 60)
    mode = user_modes.get(update.effective_user.id, "общий")
    profile = get_profile(update.effective_user.id)
    has_profile = "есть" if profile and (profile.get("age") or profile.get("chronic")) else "нет"
    await update.message.reply_text(
        f"Доктор Пётр онлайн\n"
        f"PID: {os.getpid()}\n"
        f"Аптайм: {hours}ч {minutes}м {seconds}с\n"
        f"Режим: {mode}\n"
        f"Профиль пациента: {has_profile}\n"
        f"Сообщений в истории: {len(user_history)}"
    )


async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    uid = update.effective_user.id
    user_history.clear()
    _save_history()
    user_modes.pop(uid, None)
    await update.message.reply_text("История и режим очищены.")


async def cmd_profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    uid = update.effective_user.id
    args = ctx.args

    if not args:
        profile = get_profile(uid)
        if profile:
            await update.message.reply_text(
                f"Твой профиль:\n{profile_summary(profile)}\n\n"
                "Обновить поле:\n"
                "/profile name Владимир\n"
                "/profile age 35\n"
                "/profile sex мужской\n"
                "/profile weight 80\n"
                "/profile height 180\n"
                "/profile blood A+\n"
                "/profile chronic диабет 2 типа\n"
                "/profile allergies пенициллин\n"
                "/profile meds метформин 500мг"
            )
        else:
            await update.message.reply_text(
                "Профиль не найден. Заполни данные:\n"
                "/profile name Владимир\n"
                "/profile age 35\n"
                "/profile sex мужской\n"
                "/profile weight 80\n"
                "/profile height 180\n"
                "/profile blood A+\n"
                "/profile chronic диабет 2 типа\n"
                "/profile allergies пенициллин\n"
                "/profile meds метформин 500мг"
            )
        return

    if len(args) < 2:
        await update.message.reply_text("Использование: /profile <поле> <значение>")
        return

    field = args[0].lower()
    value = " ".join(args[1:])
    field_map = {
        "name": "name",
        "age": "age",
        "sex": "sex",
        "weight": "weight_kg",
        "height": "height_cm",
        "blood": "blood_type",
        "chronic": "chronic",
        "allergies": "allergies",
        "meds": "medications",
    }
    if field not in field_map:
        await update.message.reply_text("Поля: name, age, sex, weight, height, blood, chronic, allergies, meds")
        return

    db_field = field_map[field]
    val = value
    if db_field in ("age",):
        try:
            val = int(value)
        except ValueError:
            await update.message.reply_text("Возраст должен быть числом.")
            return
    if db_field in ("weight_kg", "height_cm"):
        try:
            val = float(value)
        except ValueError:
            await update.message.reply_text("Значение должно быть числом.")
            return

    save_profile(uid, **{db_field: val})
    await update.message.reply_text(f"Сохранено: {field} = {value}")


async def cmd_set_mode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    uid = update.effective_user.id
    command = update.message.text.split()[0].lstrip("/").split("@")[0]
    if command in MODE_PREFIXES:
        user_modes[uid] = command
        await update.message.reply_text(
            f"Режим: {command.upper()}\n{MODE_PREFIXES[command]}\n\nГотов. Задавай вопросы."
        )
    else:
        await update.message.reply_text("Неизвестный режим.")


async def _process_single_message(update: Update, user_text: str):
    thinking_msg = None
    status_task = None
    try:
        thinking_msg = await update.message.reply_text("Анализирую...")

        async def _status_updater():
            msgs = ["Всё ещё анализирую...", "Готовлю ответ...", "Финализирую заключение..."]
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
        user_history.append({"role": "user", "text": user_text[:2000]})
        sm_save(uid, "peter", "user", user_text[:5000])
        _log_conversation("user", user_text, uid)
        success, answer = await ask_claude(user_text, uid)

        if success:
            answer, mem_facts = extract_and_strip_facts(answer)
            for fact in mem_facts:
                try:
                    save_memory_entry(uid, fact.get("cat", "observation"), fact["text"])
                    log.info("Memory saved: [%s] %s", fact.get("cat"), fact["text"][:60])
                except Exception as me:
                    log.warning("Memory save failed: %s", me)
            user_history.append({"role": "assistant", "text": answer[:2000]})
            sm_save(uid, "peter", "assistant", answer[:5000])
            _save_history()
            _log_conversation("assistant", answer, uid)

        try:
            await thinking_msg.delete()
        except Exception:
            pass

        chunks = _split_message(answer)
        if not chunks:
            await update.message.reply_text("Не получил ответа. Попробуй ещё раз.")
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
            await update.message.reply_text("Произошла ошибка. Попробуй ещё раз.")
        except Exception:
            pass
    finally:
        if status_task:
            status_task.cancel()


async def _drain_queue(update: Update):
    global _processing
    while True:
        async with _processing_lock:
            if not _message_queue:
                _processing = False
                return
            queued_update, queued_text = _message_queue.popleft()

        remaining = len(_message_queue)
        if remaining > 0:
            try:
                await queued_update.message.reply_text(f"Подожди {remaining}с.")
            except Exception:
                pass

        await _process_single_message(queued_update, queued_text)


async def cmd_memory(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    uid = update.effective_user.id
    entries = get_memory_entries(uid)
    if not entries:
        await update.message.reply_text(
            "Медицинская память пуста.\n\n"
            "Добавить вручную: /remember диагноз гипертония 1 степени\n"
            "Или просто расскажи Петру о своих симптомах — он запомнит сам."
        )
        return
    grouped: dict[str, list] = {}
    for e in entries:
        grouped.setdefault(e["category"], []).append(e)
    lines = ["**Медицинская память:**\n"]
    cat_order = ["diagnosis", "symptom", "allergy", "treatment", "observation"]
    cat_icons = {"diagnosis": "🔴", "symptom": "🟡", "allergy": "⚠️", "treatment": "💊", "observation": "📝"}
    for cat in cat_order:
        if cat not in grouped:
            continue
        label = _MEMORY_CAT_LABELS.get(cat, cat)
        icon = cat_icons.get(cat, "•")
        lines.append(f"{icon} *{label}:*")
        for e in grouped[cat]:
            lines.append(f"  [{e['created_at']}] {e['text']}")
    await _safe_reply(update.message, "\n".join(lines))


async def cmd_remember(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    uid = update.effective_user.id
    if not ctx.args or len(ctx.args) < 2:
        await update.message.reply_text(
            "Использование: /remember <категория> <текст>\n\n"
            "Категории:\n"
            "  диагноз / diagnosis\n"
            "  симптом / symptom\n"
            "  лечение / treatment\n"
            "  аллергия / allergy\n"
            "  наблюдение / observation\n\n"
            "Примеры:\n"
            "/remember диагноз гипертония 1 степени\n"
            "/remember симптом боль в колене при ходьбе\n"
            "/remember аллергия пенициллин"
        )
        return
    cat_arg = ctx.args[0].lower()
    category = _MEM_CAT_MAP.get(cat_arg)
    if not category:
        await update.message.reply_text("Неизвестная категория. Используй: диагноз, симптом, лечение, аллергия, наблюдение")
        return
    text = " ".join(ctx.args[1:])
    save_memory_entry(uid, category, text)
    label = _MEMORY_CAT_LABELS.get(category, category)
    await update.message.reply_text(f"Сохранено в память:\n{label}: {text}")


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
            _message_queue.append((update, user_text))
            pos = len(_message_queue)
            await update.message.reply_text(f"В очереди ({pos}). Дойду скоро.")
            return
        _processing = True

    await _process_single_message(update, user_text)
    await _drain_queue(update)


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    err = context.error
    if isinstance(err, Conflict):
        log.debug("409 Conflict")
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
        log.error("PETER_BOT_TOKEN not set in .env")
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
    init_db()
    _load_history()

    log.info("Доктор Пётр starting, PID %d", os.getpid())

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
                log.info("Takeover attempt %d — evicting, retrying...", attempt + 1)
                time.sleep(0.5)
            else:
                log.warning("Takeover attempt %d: %s", attempt + 1, e)
                time.sleep(1)
    else:
        log.warning("Could not claim session after 10 attempts, starting anyway")

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
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(CommandHandler("remember", cmd_remember))

    for mode_name in MODE_PREFIXES:
        app.add_handler(CommandHandler(mode_name, cmd_set_mode))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    app.job_queue.run_repeating(heartbeat_job, interval=60, first=10)

    _app_ref = app

    log.info("Доктор Пётр polling started")
    try:
        app.run_polling(drop_pending_updates=False, allowed_updates=Update.ALL_TYPES)
    finally:
        _cleanup()


if __name__ == "__main__":
    main()
