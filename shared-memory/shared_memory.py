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
    """)
    conn.commit()
    conn.close()


def save_message(user_id: int, bot_name: str, role: str, content: str):
    """Сохраняет сообщение в историю."""
    conn = _get_conn()
    conn.execute(
        "INSERT INTO messages (user_id, bot_name, role, content) VALUES (?, ?, ?, ?)",
        (user_id, bot_name, role, content)
    )
    conn.commit()
    conn.close()


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


# Автоматически инициализируем БД при импорте
init_db()
