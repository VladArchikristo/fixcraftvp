#!/usr/bin/env python3
"""
Vasily Daily Report — ежедневный отчёт в 21:00
Отправляет Владимиру сухие цифры по Васе за сутки
"""

import os, json, sys, requests
from datetime import datetime, date, timezone
from pathlib import Path

# Пути
BOT_DIR = Path("/Users/vladimirprihodko/Папка тест/fixcraftvp/trading-bot")
DATA_DIR = BOT_DIR / "data"
ENV_FILE = BOT_DIR / ".env"

# Загружаем .env вручную (без зависимостей)
def load_env(path):
    env = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip().strip('"').strip("'")
    except:
        pass
    return env

env = load_env(ENV_FILE)
TOKEN = env.get("VASILY_BOT_TOKEN", "")
CHAT_ID = env.get("VASILY_CHAT_ID", "244710532")

def send_telegram(text):
    if not TOKEN:
        print("ERROR: No token")
        return False
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    r = requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }, timeout=10)
    return r.status_code == 200

def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return None

def build_report():
    today = date.today().isoformat()
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    # Портфель
    portfolio = load_json(DATA_DIR / "paper_portfolio.json") or {}
    balance = portfolio.get("balance", 1000.0)
    positions = portfolio.get("positions", [])
    history = portfolio.get("history", [])

    # Дневной P&L
    daily_pnl_data = load_json(DATA_DIR / "daily_pnl.json") or []

    # Ищем сегодняшнюю запись
    today_record = next((r for r in daily_pnl_data if r.get("date") == today), None)

    # Если нет сегодняшней — берём последнюю
    if not today_record and daily_pnl_data:
        today_record = daily_pnl_data[-1]

    day_pnl = today_record.get("pnl_day", 0) if today_record else 0
    day_pnl_pct = today_record.get("pnl_pct", 0.0) if today_record else 0.0
    day_trades = today_record.get("trades", 0) if today_record else 0

    # Сделки из истории за сегодня
    today_history = [
        t for t in history
        if t.get("closed_at", "").startswith(today)
    ]

    # Открытые позиции
    open_positions_text = ""
    if positions:
        lines = []
        for p in positions:
            entry = p.get("entry_price", 0)
            side = p.get("side", "?")
            coin = p.get("coin", "?")
            size = p.get("size_usd", 0)
            lev = p.get("leverage", 1)
            emoji = "🟢" if side == "LONG" else "🔴"
            lines.append(f"  {emoji} {coin} {side} ${size:.0f} @ {entry:.1f} x{lev}")
        open_positions_text = "\n".join(lines)
    else:
        open_positions_text = "  нет открытых позиций"

    # Закрытые сделки за день
    closed_text = ""
    if today_history:
        lines = []
        for t in today_history:
            coin = t.get("coin", "?")
            side = t.get("side", "?")
            pnl = t.get("pnl", 0)
            reason = t.get("reason", "")
            emoji = "✅" if pnl > 0 else "❌"
            lines.append(f"  {emoji} {coin} {side}: {'+' if pnl>=0 else ''}{pnl:.2f}$ ({reason})")
        closed_text = "\n".join(lines)
    else:
        closed_text = "  сделок за сутки нет"

    # Статистика из всей истории
    wins = [t for t in history if t.get("pnl", 0) > 0]
    losses = [t for t in history if t.get("pnl", 0) <= 0]
    total = len(history)
    win_rate = (len(wins) / total * 100) if total > 0 else 0
    total_pnl = sum(t.get("pnl", 0) for t in history)

    # Знак P&L
    pnl_emoji = "📈" if day_pnl >= 0 else "📉"
    day_pnl_str = f"+{day_pnl:.2f}$" if day_pnl >= 0 else f"{day_pnl:.2f}$"
    day_pct_str = f"+{day_pnl_pct:.2f}%" if day_pnl_pct >= 0 else f"{day_pnl_pct:.2f}%"
    total_pnl_str = f"+{total_pnl:.2f}$" if total_pnl >= 0 else f"{total_pnl:.2f}$"

    report = f"""📊 <b>ВАСА — ДНЕВНОЙ ОТЧЁТ</b>
{now}
━━━━━━━━━━━━━━━
{pnl_emoji} <b>Сегодня:</b> {day_pnl_str} ({day_pct_str})
💰 <b>Баланс:</b> ${balance:.2f}
📋 <b>Сделок за день:</b> {day_trades}

<b>Закрытые сделки:</b>
{closed_text}

<b>Открытые позиции:</b>
{open_positions_text}

━━━━━━━━━━━━━━━
📆 <b>Всего сделок:</b> {total}
🎯 <b>Win Rate:</b> {win_rate:.0f}% ({len(wins)}W / {len(losses)}L)
💵 <b>Итого P&L:</b> {total_pnl_str}
━━━━━━━━━━━━━━━
⚙️ Режим: paper trading"""

    return report

if __name__ == "__main__":
    report = build_report()
    print(report)
    success = send_telegram(report)
    if success:
        print("✅ Отчёт отправлен")
    else:
        print("❌ Ошибка отправки")
        sys.exit(1)
