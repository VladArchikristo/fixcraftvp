#!/usr/bin/env python3
"""
Василий Quick Scanner — Быстрый сигнальный сканер (каждые 10 мин).

Чисто алгоритмический — БЕЗ Claude, отрабатывает за ~10 сек.
Сигналит в Telegram только при СИЛЬНЫХ сигналах (score >= 30).
При ОЧЕНЬ сильном сигнале (score >= 60) — запускает полный market_scan.py.
"""

import json
import os
import sys
import time
import logging
import subprocess
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

# ─── Local modules ──────────────────────────────────────────────────────────
from hyperliquid_api import (
    fetch_market_summary, fetch_extended_market, fetch_multi_timeframe,
)
from technical_analysis import full_analysis
from strategies import (
    analyze_funding_extremes, analyze_oi_divergence,
    analyze_whale_walls, analyze_multi_timeframe,
    combine_strategies, validate_signals,
)

# ─── Конфиг ───────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")

BOT_TOKEN = os.getenv("VASILY_BOT_TOKEN", "")
CHAT_ID = int(os.getenv("VASILY_CHAT_ID", "244710532"))

# Монеты для быстрого скана (только самые ликвидные)
QUICK_COINS = ["ETH", "XRP", "AVAX"]

# Пороги сигналов
ALERT_THRESHOLD = 30       # Минимальный net_score для алерта в Telegram
FULL_SCAN_THRESHOLD = 60   # net_score для запуска полного скана с Claude

# Файл последних сигналов (чтобы не спамить одинаковыми)
SIGNALS_FILE = SCRIPT_DIR / "data" / "last_signals.json"
COOLDOWN_MINUTES = 30      # Не повторять сигнал по той же монете чаще чем раз в 30 мин

# ─── Логирование ─────────────────────────────────────────────────────────────
(SCRIPT_DIR / "logs").mkdir(parents=True, exist_ok=True)
_log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
_file_handler = RotatingFileHandler(
    SCRIPT_DIR / "logs" / "quick_scan.log", maxBytes=1 * 1024 * 1024, backupCount=2, encoding="utf-8"
)
_file_handler.setFormatter(_log_formatter)
_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.setFormatter(_log_formatter)
logging.basicConfig(level=logging.INFO, handlers=[_stdout_handler, _file_handler])
log = logging.getLogger("vasily_quick")


def load_last_signals() -> dict:
    """Загрузить последние сигналы (для дедупликации)."""
    try:
        if SIGNALS_FILE.exists():
            with open(SIGNALS_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_last_signals(signals: dict):
    """Сохранить последние сигналы."""
    SIGNALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(SIGNALS_FILE, "w") as f:
            json.dump(signals, f, indent=2)
    except Exception as e:
        log.warning("save_last_signals failed: %s", e)


def is_on_cooldown(coin: str, direction: str, last_signals: dict) -> bool:
    """Проверить, не сигналили ли недавно по этой монете+направлению."""
    key = f"{coin}_{direction}"
    last_time = last_signals.get(key)
    if not last_time:
        return False
    try:
        dt = datetime.fromisoformat(last_time)
        elapsed = (datetime.now() - dt).total_seconds() / 60
        return elapsed < COOLDOWN_MINUTES
    except Exception:
        return False


def send_telegram(text: str):
    """Отправка алерта в Telegram."""
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=15,
        )
        if resp.status_code != 200:
            # Fallback без HTML
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": CHAT_ID, "text": text},
                timeout=15,
            )
    except Exception as e:
        log.error("Telegram send failed: %s", e)


def trigger_full_scan():
    """Запустить полный market_scan.py в фоне."""
    try:
        log.info("🚀 Triggering full market_scan.py...")
        subprocess.Popen(
            ["/usr/bin/python3", str(SCRIPT_DIR / "market_scan.py")],
            cwd=str(SCRIPT_DIR),
            stdout=open(SCRIPT_DIR / "logs" / "quick_triggered_scan.log", "w"),
            stderr=subprocess.STDOUT,
        )
        log.info("Full scan triggered successfully")
    except Exception as e:
        log.error("Failed to trigger full scan: %s", e)


def format_alert(signals: list[dict], hl_market: dict) -> str:
    """Форматировать Telegram алерт."""
    now = datetime.now().strftime("%H:%M")
    lines = [f"⚡ <b>VASILY QUICK ALERT</b> [{now}]\n"]

    for sig in signals:
        coin = sig["coin"]
        direction = sig["direction"]
        net = sig["net_score"]
        rec = sig["recommendation"]
        strats = sig["strategies"]

        emoji = "🟢" if direction == "LONG" else "🔴"
        strength = "💪💪💪" if abs(net) >= 60 else "💪💪" if abs(net) >= 40 else "💪"

        price = hl_market.get(coin, {}).get("price", 0)
        funding = hl_market.get(coin, {}).get("funding_rate", 0)
        change_24h = hl_market.get(coin, {}).get("price_change_24h", 0)

        lines.append(f"{emoji} <b>{coin}</b> → {rec} {strength}")
        lines.append(f"  Score: {net:+d} | Стратегий: {len(strats)}")
        lines.append(f"  ${price:,.2f} ({change_24h:+.1f}%) | FR: {funding:+.4f}%")
        lines.append(f"  Via: {', '.join(strats)}")

        # Топ причины
        for reason in sig.get("reasons", [])[:2]:
            lines.append(f"  • {reason}")
        lines.append("")

    return "\n".join(lines)


def main():
    start = time.time()
    log.info("=== QUICK SCAN STARTED ===")

    # 1. Рыночные данные с Hyperliquid
    log.info("Fetching Hyperliquid market data...")
    hl_market = fetch_market_summary(QUICK_COINS)
    if not hl_market:
        log.error("Hyperliquid unavailable, aborting quick scan")
        return

    log.info("Got data for %d coins", len(hl_market))

    # 2. Extended data (OI, predicted funding, cascades, whale walls)
    log.info("Fetching extended data...")
    extended_data = {}
    try:
        extended_data = fetch_extended_market(QUICK_COINS) or {}
    except Exception as e:
        log.warning("Extended data failed: %s", e)

    # 3. Quick TA (только 1h таймфрейм, для скорости)
    log.info("Quick TA (1h only)...")
    ta_data = {}
    confluence_data = {}
    for coin in QUICK_COINS[:7]:
        try:
            mtf = fetch_multi_timeframe(coin)
            candles_1h = mtf.get("1h", [])
            if candles_1h and len(candles_1h) >= 30:
                analysis = full_analysis(candles_1h)
                if analysis:
                    ta_data[coin] = analysis

            # Quick 4h for confluence
            candles_4h = mtf.get("4h", [])
            ta_4h = None
            if candles_4h and len(candles_4h) >= 30:
                ta_4h = full_analysis(candles_4h)

            # Confluence
            if coin in ta_data:
                conf = analyze_multi_timeframe(ta_data[coin], ta_4h)
                if conf.get("confluence_score", 0) > 0:
                    confluence_data[coin] = conf

        except Exception as e:
            log.warning("Quick TA %s failed: %s", coin, e)

    # 4. Strategy signals
    log.info("Running strategies...")
    funding_data = hl_market
    pred_funding = extended_data.get("predicted_funding", {})
    funding_hist = extended_data.get("funding_history", {})
    oi_analysis = extended_data.get("oi_analysis", {})
    cascades = extended_data.get("liquidation_cascades", {})
    whale_walls_data = extended_data.get("whale_walls", {})

    funding_signals = analyze_funding_extremes(funding_data, pred_funding, funding_hist)
    oi_signals = analyze_oi_divergence(funding_data, oi_analysis, cascades)
    whale_signals = analyze_whale_walls(whale_walls_data, funding_data)

    combined = combine_strategies(
        funding_signals, oi_signals, whale_signals, [],
        confluence_data, ta_data,
    )
    combined = validate_signals(combined, ta_data)

    # 5. Фильтруем по порогу
    strong_signals = [s for s in combined if abs(s["net_score"]) >= ALERT_THRESHOLD]
    very_strong = [s for s in combined if abs(s["net_score"]) >= FULL_SCAN_THRESHOLD]

    elapsed = time.time() - start
    log.info("Quick scan done in %.1fs. Signals: %d strong, %d very strong",
             elapsed, len(strong_signals), len(very_strong))

    if not strong_signals:
        log.info("No strong signals — silent exit")
        # Сохраняем краткий лог даже без сигналов
        _save_quick_log(combined, elapsed)
        return

    # 6. Дедупликация — не спамить одинаковыми сигналами
    last_signals = load_last_signals()
    new_signals = []
    for sig in strong_signals:
        if not is_on_cooldown(sig["coin"], sig["direction"], last_signals):
            new_signals.append(sig)
            key = f"{sig['coin']}_{sig['direction']}"
            last_signals[key] = datetime.now().isoformat()

    if not new_signals:
        log.info("All signals on cooldown — silent exit")
        _save_quick_log(combined, elapsed)
        return

    save_last_signals(last_signals)

    # 7. Telegram алерт
    log.info("Sending alert for %d signals...", len(new_signals))
    alert = format_alert(new_signals, hl_market)
    send_telegram(alert)

    # 8. Если очень сильный сигнал — запустить полный скан с Claude
    if very_strong:
        coins_str = ", ".join(s["coin"] for s in very_strong)
        log.info("VERY STRONG signals (%s) — triggering full scan!", coins_str)
        send_telegram(f"🚀 <b>Сигнал очень сильный!</b> ({coins_str})\nЗапускаю полный анализ с Claude...")
        trigger_full_scan()

    _save_quick_log(combined, elapsed)


def _save_quick_log(combined: list, elapsed: float):
    """Сохранить краткий лог для аналитики."""
    log_dir = SCRIPT_DIR / "data" / "quick_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    log_file = log_dir / f"quick_{ts}.json"
    try:
        data = {
            "time": datetime.now().isoformat(),
            "elapsed_sec": round(elapsed, 1),
            "signals_count": len(combined),
            "strong_count": sum(1 for s in combined if abs(s.get("net_score", 0)) >= ALERT_THRESHOLD),
            "top_signals": [
                {"coin": s["coin"], "direction": s["direction"], "net_score": s["net_score"],
                 "rec": s["recommendation"], "strategies": s["strategies"]}
                for s in combined[:5]
            ],
        }
        with open(log_file, "w") as f:
            json.dump(data, f, indent=2)

        # Чистим старые — оставляем 100
        logs = sorted(log_dir.glob("quick_*.json"))
        for old in logs[:-100]:
            old.unlink()
    except Exception as e:
        log.warning("save quick log failed: %s", e)


if __name__ == "__main__":
    main()
