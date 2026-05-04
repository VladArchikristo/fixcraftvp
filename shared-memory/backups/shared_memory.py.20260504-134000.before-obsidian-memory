#!/usr/bin/env python3
"""
Общая SQLite память для всех ботов проекта fixcraftvp.

Использование в боте:
    import sys
    sys.path.insert(0, '/Users/vladimirprihodko/Папка тест/fixcraftvp/shared-memory')
    from shared_memory import save_message, get_history, clear_history, save_profile, get_profile
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "memory.db")


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Создаёт таблицы если не существуют."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            bot_name TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id, bot_name, created_at);

        CREATE TABLE IF NOT EXISTS profiles (
            user_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, key)
        );

        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            bot_name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            fact TEXT NOT NULL,
            source TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_facts_user ON facts(user_id, bot_name, category);

        CREATE TABLE IF NOT EXISTS session_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            bot_name TEXT NOT NULL,
            summary TEXT NOT NULL,
            message_count INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON session_summaries(user_id, bot_name, created_at);
    """)
    conn.commit()
    conn.close()


def save_message(user_id: int, bot_name: str, role: str, content: str):
    """Сохраняет сообщение в историю. Автоматически детектирует границы сессий."""
    conn = _get_conn()

    # Авто-детекция сессий: если прошло >30 мин с последнего сообщения — сохраняем резюме старой сессии
    if role == "user":
        try:
            _auto_detect_session(conn, user_id, bot_name)
        except Exception:
            pass  # не блокируем основную логику

    conn.execute(
        "INSERT INTO messages (user_id, bot_name, role, content) VALUES (?, ?, ?, ?)",
        (user_id, bot_name, role, content)
    )
    conn.commit()
    conn.close()


# Порог определения новой сессии (секунды)
SESSION_GAP_SECONDS = 1800  # 30 минут
MIN_MESSAGES_FOR_SUMMARY = 4  # минимум сообщений для создания резюме


def _auto_detect_session(conn, user_id: int, bot_name: str):
    """Проверяет, не началась ли новая сессия (пауза >30 мин). Если да — резюмирует предыдущую."""
    last_msg = conn.execute(
        """SELECT created_at FROM messages
           WHERE user_id=? AND bot_name=?
           ORDER BY created_at DESC LIMIT 1""",
        (user_id, bot_name)
    ).fetchone()

    if not last_msg:
        return

    from datetime import datetime, timezone
    last_time_str = last_msg["created_at"]
    try:
        last_time = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        try:
            last_time = datetime.fromisoformat(last_time_str)
            if last_time.tzinfo is None:
                last_time = last_time.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return

    now_utc = datetime.now(timezone.utc)
    gap = (now_utc - last_time).total_seconds()
    if gap < SESSION_GAP_SECONDS:
        return

    # Считаем сообщения с последнего резюме
    last_summary = conn.execute(
        """SELECT created_at FROM session_summaries
           WHERE user_id=? AND bot_name=?
           ORDER BY created_at DESC LIMIT 1""",
        (user_id, bot_name)
    ).fetchone()

    if last_summary:
        summary_time = last_summary["created_at"]
        messages = conn.execute(
            """SELECT role, content, created_at FROM messages
               WHERE user_id=? AND bot_name=? AND created_at > ?
               ORDER BY created_at ASC""",
            (user_id, bot_name, summary_time)
        ).fetchall()
    else:
        messages = conn.execute(
            """SELECT role, content, created_at FROM messages
               WHERE user_id=? AND bot_name=?
               ORDER BY created_at ASC""",
            (user_id, bot_name)
        ).fetchall()

    if len(messages) < MIN_MESSAGES_FOR_SUMMARY:
        return

    # Генерируем резюме из сообщений
    summary = _generate_summary(messages)
    conn.execute(
        "INSERT INTO session_summaries (user_id, bot_name, summary, message_count) VALUES (?, ?, ?, ?)",
        (user_id, bot_name, summary, len(messages))
    )
    conn.commit()


def _generate_summary(messages) -> str:
    """Генерирует краткое резюме сессии из сообщений (без AI, чистая экстракция)."""
    user_msgs = [m for m in messages if m["role"] == "user"]
    bot_msgs = [m for m in messages if m["role"] == "assistant"]

    # Временной диапазон
    if messages:
        first_time = str(messages[0]["created_at"])[:16].replace("T", " ")
        last_time = str(messages[-1]["created_at"])[:16].replace("T", " ")
        time_range = f"{first_time} — {last_time}"
    else:
        time_range = "?"

    # Извлекаем темы из пользовательских сообщений (первые 8 слов каждого)
    topics = []
    seen = set()
    for m in user_msgs:
        text = m["content"].strip()
        if len(text) < 5:
            continue
        # Убираем команды
        if text.startswith("/"):
            topic = text.split()[0]
        else:
            words = text.split()[:8]
            topic = " ".join(words)
            if len(topic) > 80:
                topic = topic[:80] + "…"
        topic_key = topic.lower()[:30]
        if topic_key not in seen:
            seen.add(topic_key)
            topics.append(topic)

    # Ограничиваем до 5 тем
    topics = topics[:5]

    parts = [
        f"{len(messages)} сообщ. ({time_range})",
    ]
    if topics:
        parts.append("Темы: " + "; ".join(topics))

    return " | ".join(parts)


def get_history(user_id: int, bot_name: str, limit: int = 20) -> list:
    """Возвращает последние N сообщений для пользователя в формате [{role, content}]."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT role, content FROM messages
           WHERE user_id=? AND bot_name=?
           ORDER BY created_at DESC LIMIT ?""",
        (user_id, bot_name, limit)
    ).fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def clear_history(user_id: int, bot_name: str):
    """Очищает историю пользователя для конкретного бота."""
    conn = _get_conn()
    conn.execute("DELETE FROM messages WHERE user_id=? AND bot_name=?", (user_id, bot_name))
    conn.commit()
    conn.close()


def save_profile(user_id: int, key: str, value: str):
    """Сохраняет профиль пользователя (имя, знак, предпочтения и т.д.)."""
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO profiles (user_id, key, value, updated_at) VALUES (?, ?, ?, ?)",
        (user_id, key, value, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_profile(user_id: int) -> dict:
    """Возвращает весь профиль пользователя из общей таблицы profiles."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT key, value FROM profiles WHERE user_id=?", (user_id,)
    ).fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


# ===================== LEVEL 2: ФАКТЫ =====================

def save_fact(user_id: int, bot_name: str, fact: str, category: str = "general", source: str = None):
    """Сохраняет ключевой факт. Если такой факт уже есть — обновляет timestamp."""
    conn = _get_conn()
    # Проверяем дубликат (точное совпадение текста)
    existing = conn.execute(
        "SELECT id FROM facts WHERE user_id=? AND bot_name=? AND fact=?",
        (user_id, bot_name, fact)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE facts SET updated_at=?, category=? WHERE id=?",
            (datetime.now().isoformat(), category, existing["id"])
        )
    else:
        conn.execute(
            "INSERT INTO facts (user_id, bot_name, category, fact, source) VALUES (?, ?, ?, ?, ?)",
            (user_id, bot_name, category, fact, source)
        )
    conn.commit()
    conn.close()


def get_facts(user_id: int, bot_name: str, category: str = None, limit: int = 50) -> list:
    """Возвращает факты. Если category=None — все факты. Формат: [{category, fact, updated_at}]."""
    conn = _get_conn()
    if category:
        rows = conn.execute(
            """SELECT category, fact, updated_at FROM facts
               WHERE user_id=? AND bot_name=? AND category=?
               ORDER BY updated_at DESC LIMIT ?""",
            (user_id, bot_name, category, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT category, fact, updated_at FROM facts
               WHERE user_id=? AND bot_name=?
               ORDER BY updated_at DESC LIMIT ?""",
            (user_id, bot_name, limit)
        ).fetchall()
    conn.close()
    return [{"category": r["category"], "fact": r["fact"], "updated_at": r["updated_at"]} for r in rows]


def get_all_facts(user_id: int, limit: int = 100) -> list:
    """Возвращает факты от ВСЕХ ботов — для кросс-бот памяти."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT bot_name, category, fact, updated_at FROM facts
           WHERE user_id=?
           ORDER BY updated_at DESC LIMIT ?""",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [{"bot_name": r["bot_name"], "category": r["category"], "fact": r["fact"], "updated_at": r["updated_at"]} for r in rows]


def delete_fact(user_id: int, bot_name: str, fact: str):
    """Удаляет конкретный факт."""
    conn = _get_conn()
    conn.execute(
        "DELETE FROM facts WHERE user_id=? AND bot_name=? AND fact=?",
        (user_id, bot_name, fact)
    )
    conn.commit()
    conn.close()


def count_facts(user_id: int, bot_name: str) -> int:
    """Количество фактов у бота."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM facts WHERE user_id=? AND bot_name=?",
        (user_id, bot_name)
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


# ===================== LEVEL 3: РЕЗЮМЕ СЕССИЙ =====================

def save_session_summary(user_id: int, bot_name: str, summary: str, message_count: int = 0):
    """Сохраняет краткое резюме завершённой сессии."""
    conn = _get_conn()
    conn.execute(
        "INSERT INTO session_summaries (user_id, bot_name, summary, message_count) VALUES (?, ?, ?, ?)",
        (user_id, bot_name, summary, message_count)
    )
    conn.commit()
    conn.close()


def get_session_summaries(user_id: int, bot_name: str, limit: int = 5) -> list:
    """Возвращает последние N резюме сессий."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT summary, message_count, created_at FROM session_summaries
           WHERE user_id=? AND bot_name=?
           ORDER BY created_at DESC LIMIT ?""",
        (user_id, bot_name, limit)
    ).fetchall()
    conn.close()
    return [{"summary": r["summary"], "message_count": r["message_count"], "created_at": r["created_at"]} for r in reversed(rows)]


def build_memory_prompt(user_id: int, bot_name: str) -> str:
    """Строит блок памяти для system prompt: факты + последние сессии. ~500-800 токенов."""
    parts = []

    # Факты (Level 2)
    facts = get_facts(user_id, bot_name, limit=30)
    if facts:
        parts.append("=== ДОЛГОСРОЧНАЯ ПАМЯТЬ (ключевые факты) ===")
        by_cat = {}
        for f in facts:
            by_cat.setdefault(f["category"], []).append(f["fact"])
        for cat, items in by_cat.items():
            parts.append(f"[{cat}]")
            for item in items[:10]:
                parts.append(f"  • {item}")

    # Кросс-бот факты (от других ботов — только УНИКАЛЬНЫЕ, которых у этого бота нет)
    own_facts_set = {f["fact"] for f in facts} if facts else set()
    all_facts = get_all_facts(user_id, limit=100)
    cross_facts = [f for f in all_facts if f["bot_name"] != bot_name and f["fact"] not in own_facts_set][:10]
    if cross_facts:
        parts.append("\n=== ФАКТЫ ОТ ДРУГИХ БОТОВ ===")
        seen = set()
        for f in cross_facts:
            if f["fact"] not in seen:
                seen.add(f["fact"])
                parts.append(f"  [{f['bot_name']}] {f['fact']}")

    # Резюме сессий (Level 3)
    sessions = get_session_summaries(user_id, bot_name, limit=3)
    if sessions:
        parts.append("\n=== ПРЕДЫДУЩИЕ СЕССИИ ===")
        for s in sessions:
            date = s["created_at"][:16].replace("T", " ") if s["created_at"] else "?"
            parts.append(f"[{date}] ({s['message_count']} сообщ.) {s['summary']}")

    return "\n".join(parts) if parts else ""


# ===================== SYMPHONY: TASK QUEUE =====================

def init_tasks():
    """Создаёт таблицу tasks если не существует."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            github_id   INTEGER UNIQUE,
            title       TEXT NOT NULL,
            body        TEXT,
            label       TEXT,
            status      TEXT DEFAULT 'pending',
            blocked_by  TEXT,
            result      TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status, label);
    """)
    conn.commit()
    conn.close()


def add_task(github_id: int, title: str, body: str, label: str, blocked_by=None):
    """Добавляет задачу в очередь (если не существует)."""
    import json
    conn = _get_conn()
    conn.execute(
        """INSERT OR IGNORE INTO tasks (github_id, title, body, label, blocked_by)
           VALUES (?, ?, ?, ?, ?)""",
        (github_id, title, body, label, json.dumps(blocked_by) if blocked_by else None)
    )
    conn.commit()
    conn.close()


def get_pending_tasks(label: str = None) -> list:
    """Возвращает незаблокированные pending задачи."""
    conn = _get_conn()
    if label:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE status='pending' AND label=? ORDER BY created_at ASC",
            (label,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE status='pending' ORDER BY created_at ASC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_task_status(github_id: int, status: str, result: str = None):
    """Обновляет статус задачи."""
    conn = _get_conn()
    conn.execute(
        "UPDATE tasks SET status=?, result=?, updated_at=CURRENT_TIMESTAMP WHERE github_id=?",
        (status, result, github_id)
    )
    conn.commit()
    conn.close()


def get_running_tasks_count() -> int:
    """Количество задач в статусе running."""
    conn = _get_conn()
    row = conn.execute("SELECT COUNT(*) as cnt FROM tasks WHERE status='running'").fetchone()
    conn.close()
    return row["cnt"] if row else 0


# Автоматически инициализируем БД при импорте
init_db()
init_tasks()
