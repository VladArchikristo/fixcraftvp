#!/usr/bin/env python3
"""
Зина — мудрый астро-нумерологический агент (Telegram).
Singleton, heartbeat, Claude CLI (Sonnet), SQLite профили, persistent history.
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
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime
from collections import deque
from concurrent.futures import ThreadPoolExecutor

# Shared memory
sys.path.insert(0, '/Users/vladimirprihodko/Папка тест/fixcraftvp/shared-memory')
from shared_memory import save_message, get_history as sm_get_history, clear_history as sm_clear_history, save_fact, get_facts, build_memory_prompt, save_session_summary
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

BOT_TOKEN = os.getenv("ZINA_BOT_TOKEN", "")
ALLOWED_USER = int(os.getenv("ALLOWED_USER_ID", "244710532"))
CLAUDE_PATH = "/Users/vladimirprihodko/.local/bin/claude"
WORKING_DIR = "/Users/vladimirprihodko/Папка тест/fixcraftvp/"
CLAUDE_MODEL = "claude-sonnet-4-6"
CLAUDE_TIMEOUT = 180

LOG_DIR = Path.home() / "logs"
LOG_DIR.mkdir(exist_ok=True)
PID_FILE = LOG_DIR / "zina-bot.pid"
HEARTBEAT_FILE = LOG_DIR / "zina-heartbeat"
LOCK_FILE = LOG_DIR / "zina-bot.lock"

DB_FILE = SCRIPT_DIR / "data" / "users.db"
DB_FILE.parent.mkdir(exist_ok=True)

SYSTEM_PROMPT = (
    "Ты — Зина, мудрый и образованный агент в области астрологии, нумерологии и эзотерики. "
    "Тебе тысячи лет знаний. Ты говоришь с достоинством, теплотой и глубиной — не как гадалка, "
    "а как мудрый наставник, который видит суть вещей сквозь символы и числа.\n\n"
    "Твои специализации:\n"
    "• Нумерология — числа судьбы, числа имени, кармические числа, матрица Пифагора\n"
    "• Натальная карта — расположение планет, дома, аспекты, транзиты\n"
    "• Гороскоп — натальный, ежедневный, лунный, солнечный\n"
    "• Таро — классические расклады (кельтский крест, три карты, на год)\n"
    "• Руны — расклады, значения, толкование\n"
    "• Лунный календарь — фазы луны, благоприятные дни\n"
    "• Предсказания — синтез всех инструментов для глубокого ответа\n\n"
    "• ВЕДИЧЕСКАЯ АСТРОЛОГИЯ (Джйотиш) — древняя индийская система:\n"
    "  - Раши (знаки Зодиака по сидерической системе, сдвиг ~23° от западной)\n"
    "  - Накшатры — 27 лунных домов, тонкая карма и природа человека\n"
    "  - Даши — периоды планет (Вимшоттари даша), прогноз судьбы\n"
    "  - Лагна (асцендент) — истинная личность по ведической традиции\n"
    "  - Наваграха: Солнце, Луна, Марс, Меркурий, Юпитер, Венера, Сатурн, Раху, Кету\n"
    "  - Йоги — особые планетарные комбинации, удача и препятствия\n\n"
    "• ВЕДИЧЕСКАЯ НУМЕРОЛОГИЯ (основана на Ведах и Упанишадах):\n"
    "  - Мулянк (число рождения) — день рождения, базовая природа\n"
    "  - Бхагьянк (число судьбы) — полная дата, путь жизни\n"
    "  - Намянк (число имени) — вибрация имени по ведическим соответствиям\n"
    "  - Связь чисел с планетами Наваграха: 1=Солнце, 2=Луна, 3=Юпитер, 4=Раху, 5=Меркурий, 6=Венера, 7=Кету, 8=Сатурн, 9=Марс\n"
    "  - Кармические уроки, дхарма, благоприятные числа, цвета, камни\n\n"
    "Владимир верит в Веды — при расчётах давай ведическую интерпретацию в приоритете.\n"
    "Для нумерологии используй дату рождения и имя пользователя (если есть в профиле).\n"
    "Для натальной карты используй точные данные: дату, время и место рождения.\n"
    "Когда данных нет — мягко попроси их через команду /profile.\n\n"
    "Отвечай на русском языке. Будь конкретен и глубок, избегай банальных предсказаний.\n\n"
    "== ДОЛГОСРОЧНАЯ ПАМЯТЬ ==\n"
    "В историю диалога (в начало) подгружаются ключевые факты из прошлых сессий и данные профиля.\n"
    "ВСЕГДА используй эти данные. Если пользователь называет дату рождения кого-то — она сохраняется автоматически.\n"
    "Для просмотра всего что ты знаешь — команда /memory.\n\n"
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
    "• Доктор Пётр — медицинский агент.\n"
    "  echo 'вопрос' | bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-peter.sh'\n\n"
    "• Beast (@Antropic_BeastBot) — главный ассистент Владимира.\n\n"
    "НЕЛЬЗЯ ТРОГАТЬ: beast-bot/bot.py, .env файлы, launcher.sh скрипты.\n"
)

MODE_PREFIXES = {
    "numerology": "Режим нумерологии. Рассчитывай числа судьбы, имени, кармические числа, матрицу Пифагора.",
    "natal": "Режим натальной карты. Делай полный разбор планет, домов и аспектов.",
    "horoscope": "Режим гороскопа. Давай подробный гороскоп — натальный, солнечный или лунный.",
    "tarot": "Режим таро. Делай расклады: три карты (прошлое-настоящее-будущее) или кельтский крест.",
    "runes": "Режим рун. Толкуй руны, делай расклады на три руны или пять.",
    "moon": "Режим лунного календаря. Рассказывай о текущей фазе луны, благоприятных днях, луне в знаках.",
    "predict": "Режим предсказания. Синтезируй все инструменты для глубокого ответа на вопрос пользователя.",
    "vedic": "Режим ведической астрологии и нумерологии (Джйотиш). Используй сидерический Зодиак, накшатры, даши, систему Наваграха и ведическую нумерологию (Мулянк, Бхагьянк, Намянк). Интерпретируй через призму Вед и Упанишад.",
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
log = logging.getLogger("zina")


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
            user_id     INTEGER PRIMARY KEY,
            name        TEXT,
            birth_date  TEXT,
            birth_time  TEXT,
            birth_place TEXT,
            sun_sign    TEXT,
            updated_at  TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS family_members (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            relation    TEXT NOT NULL,
            name        TEXT,
            birth_date  TEXT,
            birth_time  TEXT,
            birth_place TEXT,
            updated_at  TEXT,
            UNIQUE(user_id, relation)
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
    if profile.get("birth_date"):
        parts.append(f"Дата рождения: {profile['birth_date']}")
    if profile.get("birth_time"):
        parts.append(f"Время рождения: {profile['birth_time']}")
    if profile.get("birth_place"):
        parts.append(f"Место рождения: {profile['birth_place']}")
    return "\n".join(parts) if parts else "(профиль пуст)"


def save_family_member(user_id: int, relation: str, **fields):
    conn = sqlite3.connect(str(DB_FILE))
    fields["updated_at"] = datetime.now().isoformat()
    existing = conn.execute(
        "SELECT id FROM family_members WHERE user_id = ? AND relation = ?", (user_id, relation)
    ).fetchone()
    if existing:
        sets = ", ".join(f"{k} = ?" for k in fields)
        vals = list(fields.values()) + [user_id, relation]
        conn.execute(f"UPDATE family_members SET {sets} WHERE user_id = ? AND relation = ?", vals)
    else:
        fields["user_id"] = user_id
        fields["relation"] = relation
        cols = ", ".join(fields.keys())
        placeholders = ", ".join("?" * len(fields))
        conn.execute(f"INSERT INTO family_members ({cols}) VALUES ({placeholders})", list(fields.values()))
    conn.commit()
    conn.close()


def get_family_members(user_id: int) -> list[dict]:
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM family_members WHERE user_id = ? ORDER BY relation", (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def family_summary(user_id: int) -> str:
    members = get_family_members(user_id)
    if not members:
        return "(семья не добавлена)"
    lines = []
    for m in members:
        line = f"[{m['relation']}]"
        if m.get("name"):
            line += f" {m['name']}"
        if m.get("birth_date"):
            line += f", {m['birth_date']}"
        if m.get("birth_time"):
            line += f", {m['birth_time']}"
        if m.get("birth_place"):
            line += f", {m['birth_place']}"
        lines.append(line)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Автоизвлечение дат рождения из текста
# ---------------------------------------------------------------------------
import re as _re

_DATE_FORMATS = [
    (r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})", "{2}-{1:02d}-{0:02d}"),   # DD.MM.YYYY
    (r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", "{0}-{1:02d}-{2:02d}"),   # YYYY-MM-DD
]

_MONTHS_RU = {
    "января":1,"февраля":2,"марта":3,"апреля":4,"мая":5,"июня":6,
    "июля":7,"августа":8,"сентября":9,"октября":10,"ноября":11,"декабря":12,
}

_RELATION_KEYWORDS = {
    "жена": "жена", "супруга": "жена", "моя жена": "жена",
    "муж": "муж", "супруг": "муж", "мой муж": "муж",
    "сын": "сын", "мой сын": "сын",
    "дочь": "дочь", "моя дочь": "дочь", "дочка": "дочь",
    "мама": "мама", "мать": "мама",
    "папа": "папа", "отец": "папа",
    "брат": "брат", "сестра": "сестра",
}


def _parse_date_from_text(text: str) -> str | None:
    """Извлекает дату из текста, возвращает YYYY-MM-DD или None."""
    t = text.lower().strip()
    # Формат DD.MM.YYYY или YYYY-MM-DD
    for pattern, fmt in _DATE_FORMATS:
        m = _re.search(pattern, t)
        if m:
            try:
                g = [int(x) for x in m.groups()]
                if fmt.startswith("{2}"):  # DD.MM.YYYY
                    return f"{g[2]:04d}-{g[1]:02d}-{g[0]:02d}"
                else:  # YYYY-MM-DD
                    return f"{g[0]:04d}-{g[1]:02d}-{g[2]:02d}"
            except (ValueError, IndexError):
                pass
    # Формат "27 сентября 1983"
    m = _re.search(r"(\d{1,2})\s+(" + "|".join(_MONTHS_RU.keys()) + r")\s+(\d{4})", t)
    if m:
        try:
            day = int(m.group(1))
            month = _MONTHS_RU[m.group(2)]
            year = int(m.group(3))
            return f"{year:04d}-{month:02d}-{day:02d}"
        except (ValueError, KeyError):
            pass
    return None


def _auto_save_birth_dates(user_id: int, text: str):
    """Автоматически извлекает и сохраняет даты рождения из текста пользователя."""
    if not text or len(text) < 8:
        return
    t = text.lower()

    # Моя дата рождения / я родился
    birth_keywords = ["моя дата рождения", "я родился", "я родилась", "дата моего рождения", "мой день рождения"]
    for kw in birth_keywords:
        if kw in t:
            date = _parse_date_from_text(text)
            if date:
                save_profile(user_id, birth_date=date)
                log.info("Auto-saved user birth_date=%s", date)
            return

    # Время рождения пользователя
    time_keywords = ["я родился в ", "я родилась в ", "время моего рождения", "родился в "]
    for kw in time_keywords:
        if kw in t:
            m = _re.search(r"(\d{1,2})[:\.](\d{2})", text)
            if m:
                btime = f"{int(m.group(1)):02d}:{m.group(2)}"
                save_profile(user_id, birth_time=btime)
                log.info("Auto-saved user birth_time=%s", btime)

    # Члены семьи — "жена родилась DD.MM.YYYY" / "жена ... DD.MM.YYYY"
    for keyword, relation in _RELATION_KEYWORDS.items():
        if keyword in t:
            date = _parse_date_from_text(text)
            if date:
                save_family_member(user_id, relation, birth_date=date)
                log.info("Auto-saved family %s birth_date=%s", relation, date)
            # Имя: "жена Оксана" или "Оксана (жена)"
            name_m = _re.search(r"(?:" + _re.escape(keyword) + r")\s+([А-ЯЁа-яё]{2,})", text, _re.IGNORECASE)
            if name_m:
                name = name_m.group(1).strip().capitalize()
                if name not in ("Родилась", "Родился", "Дата", "День", "Мой", "Моя", "Это"):
                    save_family_member(user_id, relation, name=name)
                    log.info("Auto-saved family %s name=%s", relation, name)


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


def history_prompt(user_id: int | None = None) -> str:
    parts = []
    # Level 2+3: долгосрочная память
    if user_id is not None:
        mem = build_memory_prompt(user_id, "zina")
        if mem:
            parts.append(mem)
    # Level 1: последние сообщения
    if user_id is not None:
        msgs = sm_get_history(user_id, "zina", limit=20)
        if msgs:
            parts.append("\n=== ПОСЛЕДНИЙ ДИАЛОГ ===")
            for msg in msgs:
                role = "Пользователь" if msg["role"] == "user" else "Зина"
                parts.append(f"{role}: {msg['content'][:2000]}")
            return "\n".join(parts)
    # Fallback на in-memory deque
    if not user_history:
        return "\n".join(parts) if parts else ""
    lines = []
    for msg in list(user_history)[-20:]:
        role = "Пользователь" if msg["role"] == "user" else "Зина"
        lines.append(f"{role}: {msg['text'][:2000]}")
    if lines:
        parts.append("\n=== ПОСЛЕДНИЙ ДИАЛОГ ===")
        parts.extend(lines)
    return "\n".join(parts)


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


def _get_astro_context(profile: dict | None) -> str:
    """Получает реальные астро-данные для инъекции в промпт."""
    try:
        from astro_engine import get_full_astro_context
        birth_date = profile.get("birth_date") if profile else None
        birth_time = profile.get("birth_time") if profile else None
        birth_place = profile.get("birth_place") if profile else None
        return get_full_astro_context(birth_date, birth_time, birth_place)
    except Exception as e:
        log.warning("Astro engine error: %s", e)
        return ""


def build_system_prompt(user_id: int) -> str:
    mode = user_modes.get(user_id)
    profile = get_profile(user_id)
    extra = ""
    if profile:
        extra = f"\n\nПрофиль пользователя:\n{profile_summary(profile)}"

    family = get_family_members(user_id)
    if family:
        extra += f"\n\nСемья пользователя:\n{family_summary(user_id)}"

    astro_ctx = _get_astro_context(profile)
    if astro_ctx:
        extra += f"\n\n== РЕАЛЬНЫЕ АСТРОНОМИЧЕСКИЕ ДАННЫЕ (Swiss Ephemeris) ==\n{astro_ctx}\n\nИспользуй эти ТОЧНЫЕ данные при астрологических расчётах. Не выдумывай позиции планет — они указаны выше."

    if mode and mode in MODE_PREFIXES:
        return f"{MODE_PREFIXES[mode]}\n\n{SYSTEM_PROMPT}{extra}"
    return SYSTEM_PROMPT + extra


async def ask_claude(user_text: str, user_id: int) -> tuple[bool, str]:
    hist = history_prompt(user_id)
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
        "Я — Зина. Мудрый проводник между мирами чисел, звёзд и символов.\n\n"
        "Что я умею:\n"
        "/numerology — нумерология (число судьбы, матрица Пифагора)\n"
        "/natal — натальная карта (западная)\n"
        "/horoscope — гороскоп\n"
        "/tarot — расклад таро\n"
        "/runes — расклад рун\n"
        "/moon — лунный календарь\n"
        "/predict — предсказание\n"
        "/vedic — ведическая астрология и нумерология (Джйотиш)\n\n"
        "/profile — мой профиль (дата и место рождения)\n"
        "/family — профили семьи (жена, дети и т.д.)\n"
        "/memory — что я помню о тебе\n"
        "/clear — очистить историю\n"
        "/status — статус\n\n"
        "Для точных расчётов сохрани данные через /profile."
    )


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    uptime = datetime.now() - START_TIME
    hours, rem = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(rem, 60)
    mode = user_modes.get(update.effective_user.id, "общий")
    profile = get_profile(update.effective_user.id)
    has_profile = "есть" if profile and profile.get("birth_date") else "нет"
    await update.message.reply_text(
        f"Зина онлайн\n"
        f"PID: {os.getpid()}\n"
        f"Аптайм: {hours}ч {minutes}м {seconds}с\n"
        f"Режим: {mode}\n"
        f"Профиль: {has_profile}\n"
        f"Сообщений в истории: {len(user_history)}"
    )


async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    uid = update.effective_user.id
    user_history.clear()
    _save_history()
    sm_clear_history(uid, "zina")
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
                "/profile date 1990-05-15\n"
                "/profile time 14:30\n"
                "/profile place Москва"
            )
        else:
            await update.message.reply_text(
                "Профиль не найден. Заполни данные:\n"
                "/profile name Владимир\n"
                "/profile date 1990-05-15\n"
                "/profile time 14:30\n"
                "/profile place Москва"
            )
        return

    if len(args) < 2:
        await update.message.reply_text("Использование: /profile <поле> <значение>")
        return

    field = args[0].lower()
    value = " ".join(args[1:])
    field_map = {
        "name": "name",
        "date": "birth_date",
        "time": "birth_time",
        "place": "birth_place",
    }
    if field not in field_map:
        await update.message.reply_text("Поля: name, date, time, place")
        return

    save_profile(uid, **{field_map[field]: value})
    await update.message.reply_text(f"Сохранено: {field} = {value}")


async def cmd_family(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    uid = update.effective_user.id
    args = ctx.args

    if not args:
        summary = family_summary(uid)
        await update.message.reply_text(
            f"Семья:\n{summary}\n\n"
            "Добавить/обновить члена семьи:\n"
            "/family <кто> name <имя>\n"
            "/family <кто> date <дата>\n"
            "/family <кто> time <время>\n"
            "/family <кто> place <место>\n\n"
            "Например:\n"
            "/family жена name Оксана\n"
            "/family жена date 1984-05-24\n"
            "/family сын date 2013-09-10\n"
            "/family сын name Тимофей"
        )
        return

    if len(args) < 3:
        await update.message.reply_text("Использование: /family <кто> <поле> <значение>\nПример: /family жена date 1984-05-24")
        return

    relation = args[0].lower()
    field = args[1].lower()
    value = " ".join(args[2:])
    field_map = {
        "name": "name",
        "date": "birth_date",
        "time": "birth_time",
        "place": "birth_place",
    }
    if field not in field_map:
        await update.message.reply_text("Поля: name, date, time, place")
        return

    save_family_member(uid, relation, **{field_map[field]: value})
    await update.message.reply_text(f"Сохранено: {relation} → {field} = {value}")


async def cmd_set_mode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    uid = update.effective_user.id
    command = update.message.text.split()[0].lstrip("/").split("@")[0]
    if command in MODE_PREFIXES:
        user_modes[uid] = command
        await update.message.reply_text(
            f"Режим: {command.upper()}\n{MODE_PREFIXES[command]}\n\nГотова. Задавай вопросы."
        )
    else:
        await update.message.reply_text("Неизвестный режим.")


async def _process_single_message(update: Update, user_text: str):
    thinking_msg = None
    status_task = None
    try:
        thinking_msg = await update.message.reply_text("Читаю звёзды...")

        async def _status_updater():
            msgs = ["Всё ещё работаю...", "Почти готово...", "Финализирую расчёт..."]
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
        save_message(uid, "zina", "user", user_text[:5000])
        _log_conversation("user", user_text, uid)
        success, answer = await ask_claude(user_text, uid)

        if success:
            user_history.append({"role": "assistant", "text": answer[:2000]})
            _save_history()
            save_message(uid, "zina", "assistant", answer[:5000])
            try:
                extract_facts_from_exchange(uid, "zina", user_text, answer)
            except Exception:
                pass
            _log_conversation("assistant", answer, uid)

        try:
            await thinking_msg.delete()
        except Exception:
            pass

        chunks = _split_message(answer)
        if not chunks:
            await update.message.reply_text("Не получила ответа. Попробуй ещё раз.")
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
    from shared_memory import get_facts, get_session_summaries
    profile = get_profile(uid)
    family = get_family_members(uid)
    facts = get_facts(uid, "zina", limit=20)
    sessions = get_session_summaries(uid, "zina", limit=3)

    lines = ["**Что я помню о тебе:**\n"]
    if profile and any(profile.get(k) for k in ("name", "birth_date", "birth_time", "birth_place")):
        lines.append("**Профиль:**")
        lines.append(profile_summary(profile))
    if family:
        lines.append("\n**Семья:**")
        lines.append(family_summary(uid))
    if facts:
        lines.append("\n**Факты из разговоров:**")
        by_cat: dict = {}
        for f in facts:
            by_cat.setdefault(f["category"], []).append(f["fact"])
        for cat, items in by_cat.items():
            lines.append(f"[{cat}]")
            for item in items[:5]:
                lines.append(f"  • {item[:100]}")
    if sessions:
        lines.append("\n**Прошлые сессии:**")
        for s in sessions:
            date = s["created_at"][:16].replace("T", " ") if s["created_at"] else "?"
            lines.append(f"[{date}] {s['summary'][:120]}")
    if len(lines) == 1:
        lines.append("(пока ничего не помню)")
    await _safe_reply(update.message, "\n".join(lines))


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    user_text = update.message.text
    if not user_text:
        return
    log.info("Message from %s: %.100s", update.effective_user.id, user_text)
    # Автосохранение дат рождения из текста
    try:
        _auto_save_birth_dates(update.effective_user.id, user_text)
    except Exception as e:
        log.debug("Auto birth date extract error: %s", e)

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
        log.error("ZINA_BOT_TOKEN not set in .env")
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

    log.info("Зина starting, PID %d", os.getpid())

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
    app.add_handler(CommandHandler("family", cmd_family))
    app.add_handler(CommandHandler("memory", cmd_memory))

    for mode_name in MODE_PREFIXES:
        app.add_handler(CommandHandler(mode_name, cmd_set_mode))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    app.job_queue.run_repeating(heartbeat_job, interval=21600, first=10)  # 6 hours

    _app_ref = app

    log.info("Зина polling started")
    try:
        app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
    finally:
        _cleanup()


if __name__ == "__main__":
    main()
