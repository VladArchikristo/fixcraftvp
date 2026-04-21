#!/usr/bin/env python3
"""
Василий Market Scanner v2 — Hyperliquid Edition
Сканирует крипторынок через РЕАЛЬНЫЕ данные Hyperliquid + полный тех.анализ.
Делает анализ через Claude CLI, обновляет paper portfolio.
"""

import json
import re
import subprocess
import sys
import os
import time
import fcntl
import logging
from logging.handlers import RotatingFileHandler
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from dotenv import load_dotenv
import html as html_mod

# ─── Local modules ──────────────────────────────────────────────────────────
try:
    from news_agent import get_news_signal, format_signal_for_vasily
    _NEWS_AGENT_AVAILABLE = True
except ImportError:
    _NEWS_AGENT_AVAILABLE = False
    get_news_signal = None
    format_signal_for_vasily = None
from hyperliquid_api import (
    fetch_market_summary, fetch_candles, fetch_funding_rates,
    fetch_extended_market, fetch_multi_timeframe, fetch_vault_summaries,
    fetch_vault_positions, fetch_perp_universe,
    CG_TO_HL, HL_TO_CG,
)
from technical_analysis import full_analysis, format_ta_report
from strategies import (
    analyze_funding_extremes, analyze_oi_divergence,
    analyze_whale_walls, analyze_vault_signals,
    analyze_multi_timeframe, analyze_btc_neutral,
    combine_strategies, format_strategy_report, validate_signals,
)

# ─── Конфиг ───────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
PORTFOLIO_FILE = SCRIPT_DIR / "data" / "paper_portfolio.json"
LOG_DIR = SCRIPT_DIR / "data" / "scan_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ─── .env ────────────────────────────────────────────────────────────────────
load_dotenv(SCRIPT_DIR / ".env")

# ─── Логирование ─────────────────────────────────────────────────────────────
_log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
_file_handler = RotatingFileHandler(
    SCRIPT_DIR / "logs" / "market_scan.log", maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_file_handler.setFormatter(_log_formatter)
_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.setFormatter(_log_formatter)
logging.basicConfig(level=logging.INFO, handlers=[_stdout_handler, _file_handler])
log = logging.getLogger("vasily_scan")

BOT_TOKEN = os.getenv("VASILY_BOT_TOKEN", "")
CHAT_ID = int(os.getenv("VASILY_CHAT_ID", "244710532"))
CLAUDE_PATH = "/Users/vladimirprihodko/.local/bin/claude"

ASSETS = ["ethereum", "ripple",
          "cardano", "avalanche-2", "polkadot", "injective-protocol", "uniswap"]

# Coins to do full TA on (top by volume on HL)
TA_COINS = ["ETH", "XRP", "AVAX"]

ASSET_SYMBOLS = {
    "ethereum": "ETH", "ripple": "XRP", "cardano": "ADA",
    "avalanche-2": "AVAX", "polkadot": "DOT", "injective-protocol": "INJ", "uniswap": "UNI"
}

# ─── Портфель ─────────────────────────────────────────────────────────────────
def load_portfolio():
    """Load portfolio with shared file lock to prevent reading during write."""
    if not PORTFOLIO_FILE.exists():
        default = {
            "initial_capital": 100,
            "cash": 100,
            "positions": [],
            "closed_trades": [],
            "scan_history": [],
            "updated_at": datetime.now().isoformat()
        }
        PORTFOLIO_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PORTFOLIO_FILE, "w") as f:
            json.dump(default, f, indent=2, ensure_ascii=False)
        return default
    lock_path = PORTFOLIO_FILE.with_suffix(".json.lock")
    lock_fd = None
    try:
        lock_fd = open(lock_path, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_SH)  # Shared lock — multiple readers OK
        with open(PORTFOLIO_FILE, "r") as f:
            data = json.load(f)
        # Normalize: "balance" → "cash" (backward compat with telegram_bot.py)
        if "cash" not in data and "balance" in data:
            data["cash"] = data.pop("balance")
        # Ensure all required keys exist
        data.setdefault("cash", 1000.0)
        data.setdefault("initial_capital", data["cash"])
        data.setdefault("positions", [])
        data.setdefault("closed_trades", [])
        data.setdefault("scan_history", [])
        return data
    except (json.JSONDecodeError, ValueError) as e:
        log.error("Portfolio file corrupted: %s", e)
        backup = PORTFOLIO_FILE.with_suffix(".json.bak")
        try:
            PORTFOLIO_FILE.rename(backup)
            log.warning("Backed up corrupted portfolio to %s", backup)
        except Exception:
            pass
        # Return fresh portfolio instead of recursion (avoids infinite loop)
        return {"initial_capital": 100, "cash": 100, "positions": [], "closed_trades": [], "scan_history": []}
    finally:
        if lock_fd:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                lock_fd.close()
            except Exception:
                pass

def save_portfolio(portfolio):
    """Save portfolio atomically with file lock to prevent race conditions.
    Uses fcntl.flock on a .lock file + atomic write (tmp → rename)."""
    import tempfile
    portfolio["updated_at"] = datetime.now().isoformat()
    lock_path = PORTFOLIO_FILE.with_suffix(".json.lock")
    lock_fd = None
    tmp_path = None
    try:
        lock_fd = open(lock_path, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)  # Exclusive lock — blocks until free
        fd, tmp_path = tempfile.mkstemp(dir=PORTFOLIO_FILE.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(portfolio, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, str(PORTFOLIO_FILE))
        tmp_path = None
    except Exception as e:
        log.error("save_portfolio failed: %s", e)
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    finally:
        if lock_fd:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                lock_fd.close()
            except Exception:
                pass

# ─── Рыночные данные ──────────────────────────────────────────────────────────
def fetch_prices():
    ids = ",".join(ASSETS)
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true&include_market_cap=true&include_24hr_vol=true"
    try:
        r = requests.get(url, timeout=15)
        return r.json()
    except Exception as e:
        log.error("fetch_prices: %s", e)
        return {}

def fetch_fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        data = r.json()
        d = data["data"][0]
        return f"{d['value']} ({d['value_classification']})"
    except (requests.RequestException, KeyError, IndexError, ValueError) as e:
        log.warning("fetch_fear_greed failed: %s", e)
        return "N/A"

def fetch_news():
    """Новости из RSS лент (CoinDesk, Cointelegraph, Decrypt) — только за последние 24ч."""
    RSS_FEEDS = [
        ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
        ("Cointelegraph", "https://cointelegraph.com/rss"),
        ("Decrypt", "https://decrypt.co/feed"),
    ]

    news = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; VasilyBot/1.0)"}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    for source, url in RSS_FEEDS:
        try:
            r = requests.get(url, timeout=15, headers=headers)
            root = ET.fromstring(r.text)
            channel = root.find("channel")
            if channel is None:
                continue
            items = channel.findall("item")[:10]
            for item in items:
                title = item.findtext("title", "").strip()
                desc = item.findtext("description", "").strip()
                desc = re.sub(r"<[^>]+>", "", desc)[:250]
                pub = item.findtext("pubDate", "")
                t_str = "--:--"
                try:
                    dt = parsedate_to_datetime(pub)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt < cutoff:
                        continue
                    t_str = dt.strftime("%H:%M")
                except Exception:
                    pass
                if title:
                    news.append({
                        "title": title,
                        "source": source,
                        "body": desc,
                        "time": t_str
                    })
        except Exception as e:
            log.warning("RSS %s: %s", source, e)
            continue

    return news[:12]

def fetch_rsi(asset_id: str, days: int = 14):
    """Calculate RSI from CoinGecko historical data. Returns RSI (0-100) or None."""
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{asset_id}/market_chart?vs_currency=usd&days={days + 1}&interval=daily"
        r = requests.get(url, timeout=15)
        data = r.json()
        prices_hist = [p[1] for p in data.get("prices", [])]
        if len(prices_hist) < days + 1:
            return None
        # Calculate daily changes
        changes = [prices_hist[i] - prices_hist[i - 1] for i in range(1, len(prices_hist))]
        gains = [c if c > 0 else 0 for c in changes]
        losses = [-c if c < 0 else 0 for c in changes]
        avg_gain = sum(gains[-days:]) / days
        avg_loss = sum(losses[-days:]) / days
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 1)
    except Exception as e:
        log.warning("fetch_rsi(%s) failed: %s", asset_id, e)
        return None


def fetch_all_rsi() -> dict:
    """Fetch RSI for key assets. Returns {symbol: rsi_value}."""
    rsi_data = {}
    key_assets = ["ethereum", "ripple", "avalanche-2", "injective-protocol"]
    for asset_id in key_assets:
        rsi = fetch_rsi(asset_id)
        if rsi is not None:
            sym = ASSET_SYMBOLS.get(asset_id, asset_id)
            rsi_data[sym] = rsi
        time.sleep(0.3)  # Rate limit CoinGecko
    return rsi_data


def fetch_btc_dominance():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=10)
        data = r.json()
        btc_dom = data["data"]["market_cap_percentage"].get("btc", 0)
        total_mcap = data["data"]["total_market_cap"].get("usd", 0)
        return round(btc_dom, 1), round(total_mcap / 1e12, 2)
    except (requests.RequestException, KeyError, ValueError) as e:
        log.warning("fetch_btc_dominance failed: %s", e)
        return "N/A", "N/A"

# ─── Получить текущую цену актива ────────────────────────────────────────────
def _get_price(asset: str, prices: dict, hl_market: dict = None) -> float:
    """Get current price for asset. Prefers Hyperliquid, falls back to CoinGecko."""
    # Try Hyperliquid first
    if hl_market and asset in hl_market:
        return hl_market[asset].get("price", 0)
    # Fallback to CoinGecko
    cg_id = next((k for k, v in ASSET_SYMBOLS.items() if v == asset), None)
    if cg_id and cg_id in prices:
        return prices[cg_id]["usd"]
    return 0


# ─── P&L расчёт + автоматическое закрытие по SL/TP ───────────────────────────
def check_sl_tp(portfolio, prices, hl_market=None):
    """Проверяем SL/TP для всех позиций. Автоматически закрываем сработавшие."""
    auto_closed = []
    remaining = []
    now = datetime.now().isoformat()

    for pos in portfolio["positions"]:
        asset = pos.get("asset") or pos.get("coin", "UNKNOWN")
        cur_price = _get_price(asset, prices, hl_market)
        if cur_price <= 0:
            remaining.append(pos)
            continue
        entry = pos.get("entry_price", 0)
        if entry <= 0:
            log.warning("Позиция %s имеет entry_price=0, пропускаем", asset)
            remaining.append(pos)
            continue

        size_usd = pos.get("size_usd", 0)
        sl = pos.get("stop_loss")
        tp = pos.get("take_profit")
        side = pos.get("side", "LONG").upper()
        trailing_pct = pos.get("trailing_stop_pct", 0)

        # --- Trailing Stop Logic ---
        if trailing_pct > 0 and sl:
            if side == "LONG" and cur_price > entry:
                # Price moved up — trail the stop loss higher
                new_sl = cur_price * (1 - trailing_pct / 100)
                if new_sl > sl:
                    log.info("Trailing SL %s LONG: $%.2f → $%.2f (price $%.2f)", asset, sl, new_sl, cur_price)
                    pos["stop_loss"] = round(new_sl, 2)
                    sl = pos["stop_loss"]
            elif side == "SHORT" and cur_price < entry:
                # Price moved down — trail the stop loss lower
                new_sl = cur_price * (1 + trailing_pct / 100)
                if new_sl < sl:
                    log.info("Trailing SL %s SHORT: $%.2f → $%.2f (price $%.2f)", asset, sl, new_sl, cur_price)
                    pos["stop_loss"] = round(new_sl, 2)
                    sl = pos["stop_loss"]

        triggered = None
        if side == "LONG":
            if sl and cur_price <= sl:
                triggered = "STOP_LOSS"
            elif tp and cur_price >= tp:
                triggered = "TAKE_PROFIT"
        else:  # SHORT
            if sl and cur_price >= sl:
                triggered = "STOP_LOSS"
            elif tp and cur_price <= tp:
                triggered = "TAKE_PROFIT"

        if triggered:
            qty = size_usd / entry
            cur_value = qty * cur_price
            # SHORT: profit when price drops; LONG: profit when price rises
            if side == "SHORT":
                pnl_usd = size_usd - cur_value
            else:
                pnl_usd = cur_value - size_usd
            pnl_pct = (pnl_usd / size_usd) * 100

            # Cash returned = original investment + profit/loss
            portfolio["cash"] += size_usd + pnl_usd
            portfolio.setdefault("closed_trades", []).append({
                "asset": asset,
                "side": side,
                "size_usd": size_usd,
                "entry_price": entry,
                "exit_price": cur_price,
                "pnl_usd": round(pnl_usd, 2),
                "pnl_pct": round(pnl_pct, 2),
                "opened_at": pos.get("opened_at", ""),
                "closed_at": now,
                "reason": f"Auto {triggered}: {'SL' if triggered == 'STOP_LOSS' else 'TP'} @ ${cur_price:.2f}"
            })
            emoji = "🛑" if triggered == "STOP_LOSS" else "🎯"
            auto_closed.append(
                f"{emoji} AUTO-CLOSE {triggered} {side} {asset} @ ${cur_price:.2f} | "
                f"P&L: {'+' if pnl_usd >= 0 else ''}{pnl_usd:.2f}$ ({'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%)"
            )
            log.info("Auto-closed %s %s by %s @ $%.2f", side, asset, triggered, cur_price)
        else:
            remaining.append(pos)

    portfolio["positions"] = remaining
    return auto_closed


# ─── Пересчёт сигналов для открытых позиций ─────────────────────────────────
def check_signal_validity(portfolio, combined_signals, prices, hl_market=None):
    """Пересчитать сигналы для открытых позиций.
    Закрыть если сигнал развернулся или ослаб."""
    closed_log = []
    remaining = []
    now = datetime.now().isoformat()

    if not combined_signals:
        return closed_log

    # Построить словарь combined по монете
    sig_by_coin = {}
    for sig in combined_signals:
        coin = sig.get("coin", "")
        sig_by_coin[coin] = sig

    for pos in portfolio["positions"]:
        asset = pos.get("asset") or pos.get("coin", "UNKNOWN")
        side = pos.get("side", "LONG").upper()
        signal = sig_by_coin.get(asset)

        if not signal:
            remaining.append(pos)
            continue

        net_score = signal.get("net_score", 0)
        direction = signal.get("direction", "NEUTRAL")
        close_reason = None

        # 1. Противоположный сигнал (обязательный выход)
        if side == "LONG" and direction == "SHORT" and abs(net_score) > 25:
            close_reason = "SIGNAL_REVERSAL"
        elif side == "SHORT" and direction == "LONG" and abs(net_score) > 25:
            close_reason = "SIGNAL_REVERSAL"
        # 2. Сигнал ослаб (score упал ниже порога)
        elif abs(net_score) < 15 and direction != side.replace("LONG", "LONG").replace("SHORT", "SHORT"):
            close_reason = "SIGNAL_EXPIRED"

        if close_reason:
            cur_price = _get_price(asset, prices, hl_market)
            if cur_price <= 0:
                remaining.append(pos)
                continue

            entry = pos.get("entry_price", 0)
            size_usd = pos.get("size_usd", 0)
            if entry <= 0 or size_usd <= 0:
                remaining.append(pos)
                continue

            qty = size_usd / entry
            cur_value = qty * cur_price
            if side == "SHORT":
                pnl_usd = size_usd - cur_value
            else:
                pnl_usd = cur_value - size_usd
            pnl_pct = (pnl_usd / size_usd) * 100

            portfolio["cash"] += size_usd + pnl_usd
            portfolio.setdefault("closed_trades", []).append({
                "asset": asset,
                "side": side,
                "size_usd": size_usd,
                "entry_price": entry,
                "exit_price": cur_price,
                "pnl_usd": round(pnl_usd, 2),
                "pnl_pct": round(pnl_pct, 2),
                "opened_at": pos.get("opened_at", ""),
                "closed_at": now,
                "reason": close_reason
            })

            if close_reason == "SIGNAL_REVERSAL":
                emoji = "⚡"
                msg = f"{emoji} SIGNAL REVERSAL: {side} {asset} закрыта @ ${cur_price:.2f} | Новый сигнал: {direction} (score: {net_score:+d}) | P&L: {'+' if pnl_usd >= 0 else ''}{pnl_usd:.2f}$ ({'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%)"
            else:
                emoji = "📉"
                msg = f"{emoji} SIGNAL EXPIRED: {side} {asset} закрыта @ ${cur_price:.2f} | Score ослаб до {net_score:+d} | P&L: {'+' if pnl_usd >= 0 else ''}{pnl_usd:.2f}$ ({'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%)"

            closed_log.append(msg)
            log.info("Signal check closed %s %s: %s (score=%d, dir=%s)", side, asset, close_reason, net_score, direction)
        else:
            log.debug("Signal valid for %s %s: score=%d, dir=%s", side, asset, net_score, direction)
            remaining.append(pos)

    portfolio["positions"] = remaining
    return closed_log


def calc_pnl(portfolio, prices, hl_market=None):
    pnl_lines = []
    total_value = portfolio["cash"]

    for pos in portfolio["positions"]:
        asset = pos.get("asset") or pos.get("coin", "UNKNOWN")
        cur_price = _get_price(asset, prices, hl_market)
        if cur_price <= 0:
            continue

        entry = pos.get("entry_price", 0)
        size_usd = pos.get("size_usd", 0)

        if entry <= 0 or size_usd <= 0:
            log.warning("Позиция %s: некорректные данные (entry=%.2f, size=%.2f)", asset, entry, size_usd)
            continue

        side = pos.get("side", "LONG").upper()
        qty = size_usd / entry
        cur_value = qty * cur_price
        # SHORT: profit when price drops; LONG: profit when price rises
        if side == "SHORT":
            pnl_usd = size_usd - cur_value
        else:
            pnl_usd = cur_value - size_usd
        pnl_pct = (pnl_usd / size_usd) * 100

        sl = pos.get("stop_loss")
        tp = pos.get("take_profit")
        sl_tp_info = f" | SL:${sl:.2f} TP:${tp:.2f}" if sl and tp else " | ⚠️ БЕЗ SL/TP"

        # Position value = original investment + P&L
        total_value += size_usd + pnl_usd
        pnl_lines.append(
            f"  {pos.get('side','LONG')} {asset}: вход ${entry:.2f} → сейчас ${cur_price:.2f} | "
            f"P&L: {'+' if pnl_usd >= 0 else ''}{pnl_usd:.2f}$ ({'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%){sl_tp_info}"
        )

    return pnl_lines, total_value

# ─── Сборка промпта для Claude ─────────────────────────────────────────────────
def build_prompt(prices, news, fear_greed, btc_dom, total_mcap, portfolio, pnl_lines, total_value,
                 rsi_data=None, hl_market=None, ta_reports=None, strategy_report=None,
                 extended_data=None, news_signal=None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # === ЦЕНЫ: Hyperliquid (первичные) + CoinGecko (fallback) ===
    price_block = ""
    if hl_market:
        for coin in TA_COINS:
            info = hl_market.get(coin, {})
            if not info:
                continue
            price = info["price"]
            ch = info.get("price_change_24h", 0)
            vol = info.get("day_volume_usd", 0)
            fr = info.get("funding_rate", 0)
            oi = info.get("open_interest_usd", 0)
            price_block += (
                f"  {coin}: ${price:,.2f} | 24h: {ch:+.2f}% | "
                f"Vol: ${vol/1e6:.0f}M | Funding: {fr:+.4f}% | "
                f"OI: ${oi/1e6:.0f}M\n"
            )
    else:
        # Fallback to CoinGecko
        for cg_id, sym in ASSET_SYMBOLS.items():
            if cg_id in prices:
                p = prices[cg_id]
                ch = p.get("usd_24h_change", 0) or 0
                vol = p.get("usd_24h_vol", 0) or 0
                price_block += f"  {sym}: ${p['usd']:,.2f} | 24h: {'+' if ch >= 0 else ''}{ch:.1f}% | Vol: ${vol/1e6:.0f}M\n"

    # === FUNDING RATES ANALYSIS ===
    funding_block = ""
    if hl_market:
        high_funding = [(c, d) for c, d in hl_market.items()
                        if abs(d.get("funding_rate", 0)) > 0.005]
        if high_funding:
            funding_block = "\nFUNDING ALERTS (>0.005%):\n"
            for coin, d in sorted(high_funding, key=lambda x: -abs(x[1]["funding_rate"])):
                fr = d["funding_rate"]
                ann = d.get("funding_annual", 0)
                direction = "LONGS PAY" if fr > 0 else "SHORTS PAY"
                funding_block += f"  {coin}: {fr:+.4f}% ({ann:+.1f}% annual) — {direction}\n"

    # === TECHNICAL ANALYSIS ===
    ta_block = ""
    if ta_reports:
        ta_block = "\n═══════════════ ПОЛНЫЙ ТЕХНИЧЕСКИЙ АНАЛИЗ ═══════════════\n"
        for report in ta_reports:
            ta_block += report + "\n"

    # === ORDER BOOK IMBALANCE ===
    book_block = ""
    if hl_market:
        imbalances = [(c, d.get("book_imbalance", 0)) for c, d in hl_market.items()
                      if abs(d.get("book_imbalance", 0)) > 10]
        if imbalances:
            book_block = "\nORDER BOOK IMBALANCE:\n"
            for coin, imb in sorted(imbalances, key=lambda x: -abs(x[1])):
                side = "BID-HEAVY (buy pressure)" if imb > 0 else "ASK-HEAVY (sell pressure)"
                book_block += f"  {coin}: {imb:+.1f}% — {side}\n"

    # === EXTENDED DATA (OI, Predicted Funding, Liquidations, Whale Walls) ===
    extended_block = ""
    if extended_data:
        # Predicted Funding
        pred = extended_data.get("predicted_funding", {})
        if pred:
            high_pred = [(c, d) for c, d in pred.items() if abs(d.get("predicted_rate", 0)) > 0.003]
            if high_pred:
                extended_block += "\nPREDICTED NEXT FUNDING:\n"
                for coin, d in sorted(high_pred, key=lambda x: -abs(x[1]["predicted_rate"]))[:8]:
                    r = d["predicted_rate"]
                    ann = d.get("predicted_annual", 0)
                    extended_block += f"  {coin}: {r:+.4f}% ({ann:+.1f}% annual)\n"

        # OI Analysis
        oi = extended_data.get("oi_analysis", {})
        if oi:
            extended_block += "\nOPEN INTEREST ANALYSIS:\n"
            for coin, d in oi.items():
                cap_str = " !! AT CAP !!" if d.get("at_cap") else f" ({d.get('pct_of_cap', 0):.0f}% of cap)"
                extended_block += f"  {coin}: OI ${d.get('oi_usd', 0)/1e6:.0f}M{cap_str}\n"

        # Liquidation Cascade Risk
        casc = extended_data.get("liquidation_cascades", {})
        risky = [(c, d) for c, d in casc.items() if d.get("cascade_risk") != "LOW"]
        if risky:
            extended_block += "\nLIQUIDATION CASCADE RISK:\n"
            for coin, d in risky:
                extended_block += f"  {coin}: {d['cascade_risk']} — premium {d['premium_pct']:+.4f}% | 24h: {d['price_change_24h']:+.2f}%\n"

        # Whale Walls
        walls = extended_data.get("whale_walls", {})
        if walls:
            extended_block += "\nWHALE WALLS IN ORDER BOOK:\n"
            for coin, entries in walls.items():
                for w in entries[:3]:
                    extended_block += f"  {coin}: {w['side']} ${w['usd_size']:,.0f} @ ${w['price']:,.2f} ({w['orders']} orders)\n"

        # Funding History Trends
        fh = extended_data.get("funding_history", {})
        if fh:
            extended_block += "\nFUNDING HISTORY (72h):\n"
            for coin, d in fh.items():
                extended_block += f"  {coin}: avg {d['avg_rate']:+.4f}% | range [{d['min_rate']:+.4f}%, {d['max_rate']:+.4f}%] | trend: {d['trend']}\n"

    # === STRATEGY INTELLIGENCE ===
    strategy_block = ""
    if strategy_report:
        strategy_block = f"\n{strategy_report}\n"

    # === NEWS AGENT SIGNAL ===
    news_signal_block = ""
    if news_signal:
        news_signal_block = "\n" + format_signal_for_vasily(news_signal) + "\n"

    # Новости
    news_block = ""
    for i, n in enumerate(news, 1):
        news_block += f"  {i}. [{n['time']}] {n['title']} ({n['source']})\n"
        if n["body"]:
            news_block += f"     {n['body'][:200]}...\n"

    # Позиции
    pos_block = "\n".join(pnl_lines) if pnl_lines else "  Нет открытых позиций"

    # Доступные активы для торговли
    available_syms = list(ASSET_SYMBOLS.values())

    prompt = f"""Ты Василий — профессиональный крипто-трейдер на Hyperliquid perpetual futures. Сейчас {now} UTC.
Все данные ниже — РЕАЛЬНЫЕ с биржи Hyperliquid (perpetual futures, не спот!).

═══════════════ РЫНОЧНЫЕ ДАННЫЕ (HYPERLIQUID) ═══════════════
ЦЕНЫ, ОБЪЁМЫ, FUNDING, OPEN INTEREST:
{price_block}{funding_block}{book_block}{extended_block}
Fear & Greed Index: {fear_greed}
BTC Dominance: {btc_dom}%
Total Market Cap: ${total_mcap}T
{ta_block}{strategy_block}{news_signal_block}
═══════════════ НОВОСТИ (последние 24ч) ═══════════════
{news_block}
═══════════════ ТЕКУЩИЙ ПОРТФЕЛЬ ═══════════════
Кэш: ${portfolio['cash']:.2f}
Начальный капитал: ${portfolio['initial_capital']:.2f}
Открытые позиции:
{pos_block}

Общая стоимость портфеля: ~${total_value:.2f}
Общий P&L: {'+' if total_value >= portfolio['initial_capital'] else ''}{total_value - portfolio['initial_capital']:.2f}$ ({'+' if total_value >= portfolio['initial_capital'] else ''}{((total_value/portfolio['initial_capital'])-1)*100:.1f}%)

═══════════════ КАК ПРИНИМАТЬ РЕШЕНИЯ ═══════════════
Используй ВСЕ доступные данные Hyperliquid для КОМПЛЕКСНОГО анализа:

**ТЕХНИЧЕСКИЙ АНАЛИЗ:**
1. **Тренд** (EMA 20/50/200, MACD) — НЕ торгуй против тренда
2. **Моментум** (RSI, MACD histogram) — ищи дивергенции
3. **Волатильность** (Bollinger Bands, ATR) — определяет размер SL/TP
4. **Объём** (volume profile, OBV) — подтверждение движения
5. **Уровни** (поддержка/сопротивление) — точки входа/выхода
6. **Multi-TF** — если 1h/4h/1d все согласны = СИЛЬНЫЙ сигнал

**HYPERLIQUID-СПЕЦИФИЧНЫЕ ДАННЫЕ:**
7. **Funding Rate** — extreme +funding = лонги перегружены → SHORT squeeze risk
8. **Predicted Funding** — если растёт → crowd всё больше в одну сторону
9. **Funding History 72h** — тренд фандинга: растёт/стабильный/падает
10. **Open Interest** — рост OI + рост цены = новые лонги; рост OI + падение = новые шорты
11. **OI vs Cap** — OI у лимита = нельзя открыть новые позы, только закрытие
12. **Liquidation Cascade Risk** — высокий = возможны резкие движения
13. **Whale Walls** — крупные ордера в стакане = зоны поддержки/сопротивления
14. **Order Book Imbalance** — перевес bid/ask показывает давление

**СТРАТЕГИИ (из Strategy Intelligence выше):**
- **Funding Extreme**: fade crowd при extreme funding (mean reversion)
- **OI Divergence**: расхождение OI/цены → potential squeeze
- **Whale Flow**: крупные стены в стакане → зоны S/R
- **Trend Following**: вход по тренду на откатах к EMA20/50
- **Mean Reversion**: oversold Bollinger/RSI = покупка, overbought = продажа
- **Breakout**: прорыв уровня с объёмом
- **Multi-TF Confluence**: все таймфреймы совпадают = высокая уверенность

ВАЖНО: Секция "STRATEGY INTELLIGENCE" выше содержит автоматически рассчитанные сигналы.
Используй их как ДОПОЛНИТЕЛЬНЫЙ вход, но принимай решение САМИ на основе ВСЕХ данных.

═══════════════ ЗАДАЧА ═══════════════
Сделай ПОЛНЫЙ профессиональный анализ:

1. **MACRO OUTLOOK** — общее настроение рынка, ключевые драйверы
2. **HYPERLIQUID FLOW** — что показывают funding trends, OI, whale walls, ликвидации
3. **INDIVIDUAL ANALYSIS** — по каждому активу: тренд, TA сигналы, уровни, риски
4. **ПОЗИЦИИ** — каждую открытую позицию: держать/закрыть/подвинуть SL
5. **ТОРГОВЫЕ РЕШЕНИЯ** (ОБЯЗАТЕЛЬНЫЙ БЛОК):

Формат строго:
OPEN_POSITION: {{"asset": "XXX", "side": "LONG/SHORT", "size_usd": NN, "stop_loss": ЦЕНА, "take_profit": ЦЕНА, "reason": "..."}}
CLOSE_POSITION: {{"asset": "XXX", "reason": "..."}}
HOLD: {{"asset": "XXX", "reason": "..."}}
NO_ACTION: {{"reason": "..."}}

ПРАВИЛА SL/TP (ВАЖНО!):
- SL ставь по ATR: 1.5-2x ATR от входа (или ближайший уровень S/R или whale wall)
- TP ставь по уровням: ближайшее сопротивление (для LONG) или поддержка (для SHORT)
- Минимальный R:R = 1:2 (TP должен быть минимум в 2 раза дальше SL)
- Whale walls = зоны S/R: ставь SL за wall, TP к следующему wall
- Используй данные из TA: Bollinger bands, EMA levels, support/resistance

RISK MANAGEMENT (автоматически проверяется системой):
- Макс 2 позиции одного направления
- Дневной лимит убытков: $10 (10% от капитала)
- Trailing Stop автоматически подтягивается
- RSI > 75 блокирует LONG, RSI < 25 блокирует SHORT
- Score < -30 = не открывать LONG, Score > +30 = не открывать SHORT
- Funding > 0.01% = осторожно с LONG (crowd is long)
- Funding < -0.01% = осторожно с SHORT (crowd is short)
- OI at cap = не открывать новые позиции на этом активе

Кэш: ${portfolio['cash']:.2f}. Максимум 30% кэша на позицию. Не открывать если кэш < $10.
Активы: {', '.join(available_syms)}

6. **ПРОГНОЗ** — 24-48 часов, конкретные уровни

Будь объективен. Конкретные числа. Без воды."""

    return prompt

# ─── Парсинг решений Claude ────────────────────────────────────────────────────

def _extract_json_object(text: str):
    """Extract first valid JSON object from text, handles nested braces."""
    start = text.find('{')
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i, ch in enumerate(text[start:], start):
        if escape:
            escape = False
            continue
        if ch == '\\' and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                raw = text[start:i + 1]
                # Cascade of fixes: try each level of repair
                for fixer in [
                    lambda t: t,                                          # raw
                    _fix_multiline_strings,                               # fix newlines in strings
                    _fix_unquoted_keys,                                   # fix unquoted keys
                    lambda t: _fix_unquoted_keys(_fix_multiline_strings(t)),  # both fixes
                ]:
                    try:
                        return json.loads(fixer(raw))
                    except (json.JSONDecodeError, ValueError):
                        continue
                return None
    return None


REQUIRED_FIELDS = {
    "OPEN": {"asset", "side", "size_usd"},
    "CLOSE": {"asset"},
    "HOLD": set(),
    "NO_ACTION": set(),
}

COMMAND_PREFIXES = {
    "OPEN_POSITION:": "OPEN",
    "CLOSE_POSITION:": "CLOSE",
    "HOLD:": "HOLD",
    "NO_ACTION:": "NO_ACTION",
}

# Regex для поиска JSON объектов в тексте (с поддержкой одного уровня вложенности)
_JSON_RE = re.compile(r'\{(?:[^{}]|\{[^{}]*\})*\}')


def _fix_unquoted_keys(text: str) -> str:
    """Fix unquoted JSON keys: {asset: "BTC"} → {"asset": "BTC"}.
    Claude sometimes returns JS-style objects instead of valid JSON."""
    # Match unquoted keys before colon (word chars, not already quoted)
    return re.sub(r'(?<=[{,])\s*([a-zA-Z_]\w*)\s*:', r' "\1":', text)


def _fix_multiline_strings(text: str) -> str:
    """Fix literal newlines inside JSON string values.
    Claude often returns multi-line reason fields like:
      "reason": "Line one.
                 Line two."
    which is invalid JSON. Replace newlines inside strings with spaces."""
    result = []
    in_string = False
    escape = False
    for ch in text:
        if escape:
            result.append(ch)
            escape = False
            continue
        if ch == '\\' and in_string:
            result.append(ch)
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
            continue
        if in_string and ch == '\n':
            result.append(' ')  # Replace newline with space inside strings
            continue
        result.append(ch)
    return ''.join(result)


def _try_parse_json(text: str):
    """Пытаемся извлечь JSON из строки, поддерживая разные форматы Claude."""
    text = text.strip()
    # Прямой парсинг
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass
    # Попытка починить unquoted keys
    try:
        fixed = _fix_unquoted_keys(text)
        return json.loads(fixed)
    except (json.JSONDecodeError, ValueError):
        pass
    # Поиск JSON внутри строки через regex
    match = _JSON_RE.search(text)
    if match:
        try:
            return json.loads(match.group())
        except (json.JSONDecodeError, ValueError):
            pass
        # Попытка починить unquoted keys в найденном JSON
        try:
            fixed = _fix_unquoted_keys(match.group())
            return json.loads(fixed)
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def parse_trading_decisions(claude_output, portfolio, prices):
    """Парсим OPEN/CLOSE/HOLD команды из ответа Claude с валидацией.
    Поддерживает как однострочный JSON так и многострочный формат."""
    actions = []

    for prefix, action_type in COMMAND_PREFIXES.items():
        search_start = 0
        while True:
            pos = claude_output.find(prefix, search_start)
            if pos == -1:
                break
            after_prefix = claude_output[pos + len(prefix):]
            # Ищем первую открывающую скобку — JSON может быть на следующей строке
            brace_pos = after_prefix.find('{')
            if brace_pos == -1:
                break
            # Используем балансировщик скобок для многострочного JSON
            data = _extract_json_object(after_prefix[brace_pos:])
            if data is None:
                log.warning("Не удалось распарсить JSON для %s: %.200s", prefix, after_prefix[:200])
                search_start = pos + len(prefix)
                continue
            # Валидация обязательных полей
            missing = REQUIRED_FIELDS[action_type] - set(data.keys())
            if missing:
                log.warning("%s: отсутствуют поля %s в %s", action_type, missing, data)
                search_start = pos + len(prefix)
                continue
            actions.append((action_type, data))
            search_start = pos + len(prefix)

    return actions

def _daily_loss(portfolio) -> float:
    """Calculate total realized loss for today's closed trades."""
    today = datetime.now().strftime("%Y-%m-%d")
    daily = 0.0
    for t in portfolio.get("closed_trades", []):
        closed_at = t.get("closed_at", "")
        if closed_at.startswith(today):
            pnl = t.get("pnl_usd", 0)
            if pnl < 0:
                daily += pnl  # negative
    return daily


DAILY_LOSS_LIMIT = -10.0  # Max $10 loss per day (10% of $100 capital)
MAX_SAME_DIRECTION = 2    # Max 2 positions in the same direction


def execute_trades(actions, portfolio, prices, hl_market=None, ta_data=None, extended_data=None):
    """Применяем торговые решения к бумажному портфелю с risk management.
    ta_data: {coin: analysis_dict} from technical_analysis module.
    extended_data: full extended market data (OI caps, cascades, etc.)."""
    trade_log = []
    now = datetime.now().isoformat()

    # --- Daily Loss Limit Check ---
    today_loss = _daily_loss(portfolio)
    if today_loss <= DAILY_LOSS_LIMIT:
        trade_log.append(f"🛑 DAILY LOSS LIMIT: потери сегодня ${today_loss:.2f} ≥ лимит ${DAILY_LOSS_LIMIT:.2f}. Новые сделки заблокированы.")
        # Still process CLOSE and HOLD, but block OPEN
        actions = [(t, d) for t, d in actions if t != "OPEN"]

    for action_type, data in actions:
        if action_type == "OPEN":
            asset = data.get("asset", "").upper()
            side = data.get("side", "LONG").upper()
            size_usd = float(data.get("size_usd", 0))
            reason = data.get("reason", "")

            # --- Дублирование: запрет открывать позицию по уже открытому активу ---
            existing = next((p for p in portfolio["positions"] if p.get("asset", "").upper() == asset), None)
            if existing:
                trade_log.append(f"🛑 SKIP OPEN {asset}: позиция уже открыта (side={existing.get('side')}, size=${existing.get('size_usd', 0):.0f})")
                continue

            # --- Correlation Filter: max 2 same-direction positions ---
            same_dir = sum(1 for p in portfolio["positions"] if p.get("side", "LONG").upper() == side)
            if same_dir >= MAX_SAME_DIRECTION:
                trade_log.append(f"⚠️ SKIP OPEN {side} {asset}: уже {same_dir} позиций {side} (лимит {MAX_SAME_DIRECTION})")
                continue

            # Проверки
            if size_usd <= 0 or size_usd > portfolio["cash"]:
                trade_log.append(f"❌ OPEN {asset}: недостаточно кэша (нужно ${size_usd:.0f}, есть ${portfolio['cash']:.0f})")
                continue

            # Лимит 30% на позицию
            max_position = portfolio["cash"] * 0.30
            if size_usd > max_position:
                log.warning("OPEN %s: size_usd $%.0f превышает 30%% лимит $%.0f, обрезаем", asset, size_usd, max_position)
                size_usd = round(max_position, 2)

            # Найти цену — Hyperliquid first, then CoinGecko
            cur_price = _get_price(asset, prices, hl_market)
            if cur_price <= 0:
                trade_log.append(f"❌ OPEN {asset}: цена не найдена")
                continue

            # RSI/Score блокировка из TA данных
            coin_ta = (ta_data or {}).get(asset)
            if coin_ta:
                ta_rsi = coin_ta.get("rsi")
                ta_score = coin_ta.get("score", 0)
                if ta_rsi and ta_rsi > 75 and side == "LONG":
                    trade_log.append(f"⚠️ SKIP OPEN LONG {asset}: RSI={ta_rsi} >75 (overbought)")
                    continue
                if ta_rsi and ta_rsi < 25 and side == "SHORT":
                    trade_log.append(f"⚠️ SKIP OPEN SHORT {asset}: RSI={ta_rsi} <25 (oversold)")
                    continue
                if ta_score < -30 and side == "LONG":
                    trade_log.append(f"⚠️ SKIP OPEN LONG {asset}: TA Score={ta_score} (bearish)")
                    continue
                if ta_score > 30 and side == "SHORT":
                    trade_log.append(f"⚠️ SKIP OPEN SHORT {asset}: TA Score={ta_score} (bullish)")
                    continue

            # Funding rate warning (from Hyperliquid)
            hl_info = (hl_market or {}).get(asset, {})
            fr = hl_info.get("funding_rate", 0)
            if fr > 0.01 and side == "LONG":
                trade_log.append(f"⚠️ WARNING {asset}: Funding {fr:+.4f}% — longs paying (crowd is long)")
            elif fr < -0.01 and side == "SHORT":
                trade_log.append(f"⚠️ WARNING {asset}: Funding {fr:+.4f}% — shorts paying (crowd is short)")

            # OI Cap check (from extended data)
            oi_info = (extended_data or {}).get("oi_analysis", {}).get(asset, {})
            if oi_info.get("at_cap"):
                trade_log.append(f"🛑 SKIP OPEN {side} {asset}: OI at cap — no new positions allowed on HL")
                continue
            elif oi_info.get("pct_of_cap", 0) > 95:
                trade_log.append(f"⚠️ WARNING {asset}: OI at {oi_info['pct_of_cap']:.0f}% of cap — near limit")

            # SL/TP — use ATR-based if available, else Claude's values, else volatility fallback
            sl = data.get("stop_loss")
            tp = data.get("take_profit")
            if not sl or not tp:
                # ATR-based SL/TP (best)
                if coin_ta and coin_ta.get("atr"):
                    atr_val = coin_ta["atr"]["atr"]
                    if not sl:
                        sl = cur_price - (1.5 * atr_val) if side == "LONG" else cur_price + (1.5 * atr_val)
                    if not tp:
                        # Use support/resistance levels if available
                        levels = coin_ta.get("levels", {})
                        if side == "LONG" and levels and levels.get("nearest_resistance"):
                            tp = levels["nearest_resistance"]
                        elif side == "SHORT" and levels and levels.get("nearest_support"):
                            tp = levels["nearest_support"]
                        else:
                            tp = cur_price + (3.0 * atr_val) if side == "LONG" else cur_price - (3.0 * atr_val)
                else:
                    # Fallback to volatility-based
                    cg_id = next((k for k, v in ASSET_SYMBOLS.items() if v == asset), None)
                    vol_24h = abs(hl_info.get("price_change_24h", 5) or
                                 (prices.get(cg_id, {}).get("usd_24h_change", 5) if cg_id else 5))
                    sl_pct = max(0.03, min(vol_24h / 100 * 1.5, 0.10))
                    tp_pct = max(0.05, min(vol_24h / 100 * 3.0, 0.30))
                    if not sl:
                        sl = cur_price * ((1 - sl_pct) if side == "LONG" else (1 + sl_pct))
                    if not tp:
                        tp = cur_price * ((1 + tp_pct) if side == "LONG" else (1 - tp_pct))

            # Ensure minimum R:R = 1:2
            sl_dist = abs(cur_price - float(sl))
            tp_dist = abs(float(tp) - cur_price)
            if sl_dist > 0 and tp_dist / sl_dist < 1.5:
                # Adjust TP to meet minimum R:R
                if side == "LONG":
                    tp = cur_price + (sl_dist * 2.0)
                else:
                    tp = cur_price - (sl_dist * 2.0)
                trade_log.append(f"📐 Adjusted TP for {asset}: R:R was < 1.5, now 1:2.0")

            # Trailing stop: ATR-based or volatility-based
            if coin_ta and coin_ta.get("atr"):
                trailing_pct = max(2.0, min(coin_ta["atr"]["atr_pct"] * 1.2, 5.0))
            else:
                vol_24h = abs(hl_info.get("price_change_24h", 3) or 3)
                trailing_pct = max(2.0, min(vol_24h * 0.8, 5.0))

            # Открываем позицию
            portfolio["cash"] -= size_usd
            portfolio["positions"].append({
                "asset": asset,
                "side": side,
                "size_usd": size_usd,
                "entry_price": cur_price,
                "stop_loss": round(float(sl), 2),
                "take_profit": round(float(tp), 2),
                "trailing_stop_pct": round(trailing_pct, 1),
                "opened_at": now
            })
            trade_log.append(f"✅ ОТКРЫТА {side} {asset} ${size_usd:.0f} @ ${cur_price:.2f} SL:${sl:.2f} TP:${tp:.2f} Trail:{trailing_pct:.0f}% | {reason}")

        elif action_type == "CLOSE":
            asset = data.get("asset", "").upper()
            reason = data.get("reason", "")

            # Найти позицию
            pos = next((p for p in portfolio["positions"] if p["asset"] == asset), None)
            if not pos:
                trade_log.append(f"❌ CLOSE {asset}: позиция не найдена")
                continue

            # Найти текущую цену — Hyperliquid first
            cur_price = _get_price(asset, prices, hl_market)
            if cur_price <= 0:
                trade_log.append(f"❌ CLOSE {asset}: цена не найдена")
                continue
            entry = pos.get("entry_price", 0)
            size_usd = pos.get("size_usd", 0)
            side_close = pos.get("side", "LONG").upper()
            if entry <= 0 or size_usd <= 0:
                trade_log.append(f"❌ CLOSE {asset}: некорректные данные позиции")
                continue
            qty = size_usd / entry
            cur_value = qty * cur_price
            # SHORT: profit when price drops; LONG: profit when price rises
            if side_close == "SHORT":
                pnl_usd = size_usd - cur_value
            else:
                pnl_usd = cur_value - size_usd
            pnl_pct = (pnl_usd / size_usd) * 100

            # Закрываем — cash returned = original + P&L
            portfolio["cash"] += size_usd + pnl_usd
            portfolio["positions"] = [p for p in portfolio["positions"] if p["asset"] != asset]
            portfolio.setdefault("closed_trades", []).append({
                "asset": asset,
                "side": pos["side"],
                "size_usd": size_usd,
                "entry_price": entry,
                "exit_price": cur_price,
                "pnl_usd": round(pnl_usd, 2),
                "pnl_pct": round(pnl_pct, 2),
                "opened_at": pos["opened_at"],
                "closed_at": now,
                "reason": reason
            })
            trade_log.append(
                f"✅ ЗАКРЫТА {pos['side']} {asset} @ ${cur_price:.2f} | "
                f"P&L: {'+' if pnl_usd >= 0 else ''}{pnl_usd:.2f}$ ({'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%) | {reason}"
            )

        elif action_type == "HOLD":
            asset = data.get("asset", "")
            reason = data.get("reason", "")
            trade_log.append(f"🔄 HOLD {asset} | {reason}")

        elif action_type == "NO_ACTION":
            reason = data.get("reason", "")
            trade_log.append(f"⏸️ NO_ACTION | {reason}")

    return trade_log

# ─── Claude CLI ────────────────────────────────────────────────────────────────
def _get_claude_env() -> dict:
    """Clean env for Claude CLI — only essentials, no stale tokens."""
    home = Path.home()
    nvm_node_bin = ""
    nvm_dir = home / ".nvm" / "versions" / "node"
    if nvm_dir.exists():
        versions = sorted(nvm_dir.iterdir(), reverse=True)
        if versions:
            nvm_node_bin = str(versions[0] / "bin")
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


def ask_claude(prompt):
    """Вызываем Claude через CLI с retry (3 попытки) и clean env.
    Убивает process group при таймауте — нет зомби-процессов."""
    import signal as _signal
    backoff = [3, 5, 10]

    for attempt in range(3):
        proc = None
        try:
            proc = subprocess.Popen(
                [CLAUDE_PATH, "-p",
                 "--model", "claude-sonnet-4-6",
                 "--output-format", "text",
                 "--max-turns", "15"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd="/Users/vladimirprihodko/Папка тест/fixcraftvp",
                env=_get_claude_env(),
                start_new_session=True,  # process group for clean kill
            )
            stdout, stderr = proc.communicate(input=prompt, timeout=180)

            if proc.returncode == 0 and stdout.strip():
                return stdout.strip()
            else:
                log.error("Claude attempt %d/3 exited %d: %s", attempt + 1, proc.returncode, (stderr or "")[:500])

        except subprocess.TimeoutExpired:
            log.warning("Claude attempt %d/3 timed out after 180 sec", attempt + 1)
            if proc:
                try:
                    os.killpg(os.getpgid(proc.pid), _signal.SIGKILL)
                    log.info("Killed Claude process group (PID %d)", proc.pid)
                except (ProcessLookupError, PermissionError):
                    try:
                        proc.kill()
                    except (ProcessLookupError, PermissionError):
                        pass
                try:
                    proc.wait(timeout=5)
                except (ChildProcessError, subprocess.TimeoutExpired):
                    pass
            if attempt == 2:  # last attempt — no retry on timeout
                return None

        except Exception as e:
            log.error("ask_claude attempt %d/3 error: %s", attempt + 1, e)

        if attempt < 2:
            delay = backoff[attempt]
            log.info("Retrying Claude in %d sec...", delay)
            time.sleep(delay)

    return None

# ─── Telegram ─────────────────────────────────────────────────────────────────
def _smart_split(text: str, limit: int = 4000) -> list[str]:
    """Split text preferring line boundaries so tables/sections stay intact."""
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        # Try to split at a blank line (section boundary) first
        split_at = text.rfind("\n\n", 0, limit)
        if split_at <= 0:
            # Fall back to any newline
            split_at = text.rfind("\n", 0, limit)
        if split_at <= 0:
            # Last resort: hard cut
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


def send_telegram(text, max_len=4000):
    """Отправка в Telegram с retry. HTML fallback → plain text если парсинг не удался."""
    chunks = _smart_split(text, max_len)
    for i, chunk in enumerate(chunks):
        sent = False
        for attempt in range(3):
            try:
                # First try HTML parse_mode
                parse_mode = "HTML" if attempt < 2 else None
                resp = requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": CHAT_ID, "text": chunk, "parse_mode": parse_mode},
                    timeout=15
                )
                if resp.status_code == 200:
                    sent = True
                    break
                # If HTTP 400 (bad markup), retry without parse_mode immediately
                if resp.status_code == 400 and attempt == 0:
                    log.warning("Telegram HTML parse failed, retrying as plain text")
                    resp2 = requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        json={"chat_id": CHAT_ID, "text": chunk},
                        timeout=15
                    )
                    if resp2.status_code == 200:
                        sent = True
                        break
                log.warning("Telegram chunk %d attempt %d: HTTP %d", i, attempt + 1, resp.status_code)
            except Exception as e:
                log.warning("Telegram chunk %d attempt %d: %s", i, attempt + 1, e)
            time.sleep(2 * (attempt + 1))
        if not sent:
            log.error("Не удалось отправить chunk %d/%d после 3 попыток", i + 1, len(chunks))
        else:
            time.sleep(0.5)

# ─── Лог ──────────────────────────────────────────────────────────────────────
def save_log(scan_result):
    try:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        log_file = LOG_DIR / f"scan_{ts}.json"
        with open(log_file, "w") as f:
            json.dump(scan_result, f, indent=2, ensure_ascii=False)

        # Чистим старые логи — оставляем последние 30
        logs = sorted(LOG_DIR.glob("scan_*.json"))
        for old in logs[:-30]:
            try:
                old.unlink()
            except OSError as e:
                log.warning("Failed to delete old scan log %s: %s", old, e)
    except Exception as e:
        log.error("save_log failed: %s", e)

# ─── Форматирование Telegram сообщения ────────────────────────────────────────
def format_telegram_message(analysis, trade_log, portfolio, prices, pnl_lines, total_value,
                            fear_greed, btc_dom, hl_market=None, ta_data=None,
                            confluence_data=None, extended_data=None):
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    # Экранируем HTML спецсимволы в анализе Claude (< > & ломают parse_mode=HTML)
    analysis_safe = html_mod.escape(analysis)
    analysis_short = analysis_safe[:3000] + "\n..." if len(analysis_safe) > 3000 else analysis_safe

    trades_text = html_mod.escape("\n".join(trade_log) if trade_log else "Действий не выполнено")
    pnl_text = html_mod.escape("\n".join(pnl_lines) if pnl_lines else "Нет открытых позиций")

    pnl_total = total_value - portfolio["initial_capital"]
    pnl_pct = ((total_value / portfolio["initial_capital"]) - 1) * 100
    pnl_emoji = "📈" if pnl_total >= 0 else "📉"

    # Цены — Hyperliquid (приоритет) + CoinGecko fallback
    prices_mini = ""
    for coin in ["ETH", "XRP", "AVAX", "INJ"]:
        if hl_market and coin in hl_market:
            info = hl_market[coin]
            ch = info.get("price_change_24h", 0)
            fr = info.get("funding_rate", 0)
            prices_mini += f"{coin} ${info['price']:,.0f} ({ch:+.1f}%) FR:{fr:+.4f}%\n"
        else:
            cg_id = next((k for k, v in ASSET_SYMBOLS.items() if v == coin), None)
            if cg_id and cg_id in prices:
                ch = prices[cg_id].get("usd_24h_change", 0) or 0
                prices_mini += f"{coin} ${prices[cg_id]['usd']:,.0f} ({ch:+.1f}%)\n"

    # TA Summary with multi-TF confluence
    ta_mini = ""
    if ta_data:
        for coin in ["ETH", "XRP", "AVAX", "INJ"]:
            ta = ta_data.get(coin)
            if ta:
                score = ta.get("score", 0)
                rec = ta.get("recommendation", "?")
                rsi = ta.get("rsi", "?")
                macd = ta.get("macd", {})
                macd_trend = macd.get("trend", "?") if macd else "?"
                conf = (confluence_data or {}).get(coin, {})
                conf_str = ""
                if conf:
                    conf_pct = conf.get("confluence_score", 0)
                    conf_dir = conf.get("direction", "?")
                    if conf_pct >= 60:
                        conf_str = f" MTF:{conf_dir}({conf_pct}%)"
                ta_mini += f"  {coin}: {score:+d} ({rec}) RSI:{rsi} MACD:{macd_trend}{conf_str}\n"

    # Extended data mini summary
    ext_mini = ""
    if extended_data:
        casc = extended_data.get("liquidation_cascades", {})
        risky = [c for c, d in casc.items() if d.get("cascade_risk") != "LOW"]
        if risky:
            ext_mini += f"  Cascade risk: {', '.join(risky)}\n"
        walls = extended_data.get("whale_walls", {})
        if walls:
            ext_mini += f"  Whale walls: {', '.join(f'{c}({len(v)})' for c, v in walls.items())}\n"
        oi = extended_data.get("oi_analysis", {})
        at_cap = [c for c, d in oi.items() if d.get("at_cap")]
        if at_cap:
            ext_mini += f"  OI AT CAP: {', '.join(at_cap)}\n"

    # Экранируем динамические данные перед вставкой в HTML
    prices_mini = html_mod.escape(prices_mini)
    ta_mini = html_mod.escape(ta_mini)
    ext_mini = html_mod.escape(ext_mini)

    # Data source indicator
    source = "📡 Hyperliquid Extended" if extended_data else ("📡 Hyperliquid" if hl_market else "🔶 CoinGecko")

    msg = f"""🤖 <b>ВАСИЛИЙ MARKET SCAN v3</b> — {now}
{source}

💰 <b>Цены + Funding:</b>
{prices_mini}
😱 F&amp;G: {fear_greed} | BTC Dom: {btc_dom}%

📊 <b>Тех.анализ (Multi-TF):</b>
{ta_mini if ta_mini else "  N/A"}
{ext_mini}

{pnl_emoji} <b>Портфель:</b>
{pnl_text}
Кэш: ${portfolio['cash']:.2f}
Итого: ${total_value:.2f} | P&amp;L: {'+' if pnl_total >= 0 else ''}{pnl_total:.2f}$ ({'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%)

🔄 <b>Сделки:</b>
{trades_text}

📊 <b>Анализ Василия:</b>
{analysis_short}"""

    return msg

# ─── Главная функция ───────────────────────────────────────────────────────────
def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] === VASILY MARKET SCAN v3 (HYPERLIQUID EXTENDED) STARTED ===")

    # 1. Загружаем портфель
    portfolio = load_portfolio()
    print("[*] Портфель загружен")

    # 2. Рыночные данные — Hyperliquid (PRIMARY) + CoinGecko (FALLBACK)
    print("[*] Получаем данные с Hyperliquid...")
    hl_market = fetch_market_summary(TA_COINS)
    if hl_market:
        print(f"[+] Hyperliquid: получены данные для {len(hl_market)} активов")
        for coin, info in sorted(hl_market.items(), key=lambda x: -x[1]["day_volume_usd"])[:5]:
            print(f"    {coin}: ${info['price']:,.2f} | 24h: {info['price_change_24h']:+.2f}% | "
                  f"Funding: {info['funding_rate']:+.4f}% | OI: ${info['open_interest_usd']/1e6:.0f}M")
    else:
        print("[!] Hyperliquid unavailable, falling back to CoinGecko")

    print("[*] Получаем цены CoinGecko (fallback + дополнение)...")
    prices = fetch_prices()
    if not prices and not hl_market:
        send_telegram("❌ Василий: не удалось получить рыночные данные. Скан отменён.")
        sys.exit(1)

    print("[*] Fear & Greed...")
    fear_greed = fetch_fear_greed()

    print("[*] Новости...")
    news = fetch_news()

    print("[*] BTC dominance...")
    btc_dom, total_mcap = fetch_btc_dominance()

    # 2b. Extended Hyperliquid data (OI, predicted funding, cascades, whale walls, funding history)
    print("[*] Расширенные данные Hyperliquid (OI, predicted funding, cascades, whales)...")
    extended_data = None
    try:
        extended_data = fetch_extended_market(TA_COINS)
        if extended_data:
            pred = extended_data.get("predicted_funding", {})
            oi = extended_data.get("oi_analysis", {})
            casc = extended_data.get("liquidation_cascades", {})
            walls = extended_data.get("whale_walls", {})
            fh = extended_data.get("funding_history", {})
            print(f"[+] Predicted funding: {len(pred)} coins")
            print(f"[+] OI analysis: {len(oi)} coins")
            print(f"[+] Cascade risk: {sum(1 for d in casc.values() if d.get('cascade_risk') != 'LOW')} at risk")
            print(f"[+] Whale walls: {sum(len(v) for v in walls.values())} detected")
            print(f"[+] Funding history: {len(fh)} coins (72h)")
    except Exception as e:
        log.warning("Extended market data failed: %s", e)

    # 2c. Полный тех.анализ по свечам Hyperliquid — MULTI-TIMEFRAME
    print("[*] Тех.анализ Multi-TF (1h + 4h + 1d)...")
    ta_data = {}  # {coin: analysis_dict} (1h primary)
    ta_4h = {}    # {coin: analysis_dict}
    ta_1d = {}    # {coin: analysis_dict}
    ta_reports = []  # formatted strings for Claude prompt
    confluence_data = {}  # {coin: confluence_result}

    for coin in TA_COINS[:7]:  # Top 7 by importance
        try:
            # Fetch all timeframes
            mtf = fetch_multi_timeframe(coin)

            # 1h (primary)
            candles_1h = mtf.get("1h", [])
            if candles_1h and len(candles_1h) >= 30:
                analysis = full_analysis(candles_1h)
                if analysis:
                    ta_data[coin] = analysis
                    ta_reports.append(format_ta_report(coin, analysis))
                    rec = analysis.get("recommendation", "?")
                    score = analysis.get("score", 0)
                    print(f"    {coin} 1h: Score={score:+d} → {rec}", end="")

            # 4h
            candles_4h = mtf.get("4h", [])
            if candles_4h and len(candles_4h) >= 30:
                analysis_4h = full_analysis(candles_4h)
                if analysis_4h:
                    ta_4h[coin] = analysis_4h
                    ta_reports.append(format_ta_report(f"{coin} (4h)", analysis_4h))
                    print(f" | 4h: {analysis_4h.get('score', 0):+d}", end="")

            # 1d
            candles_1d = mtf.get("1d", [])
            if candles_1d and len(candles_1d) >= 30:
                analysis_1d = full_analysis(candles_1d)
                if analysis_1d:
                    ta_1d[coin] = analysis_1d
                    ta_reports.append(format_ta_report(f"{coin} (1d)", analysis_1d))
                    print(f" | 1d: {analysis_1d.get('score', 0):+d}", end="")

            # Multi-TF confluence
            conf = analyze_multi_timeframe(
                ta_data.get(coin, {}),
                ta_4h.get(coin),
                ta_1d.get(coin),
            )
            if conf.get("confluence_score", 0) > 0:
                confluence_data[coin] = conf
                print(f" | Confluence: {conf['confluence_score']}% {conf['direction']}", end="")

            print()  # newline

        except Exception as e:
            log.warning("TA for %s failed: %s", coin, e)
            print()

    # 2d. Strategy Intelligence — combine all signals
    print("[*] Strategy Intelligence...")
    strategy_report = ""
    combined = []  # Initialize before try block — used later in check_signal_validity
    try:
        funding_data = hl_market or {}
        pred_funding = extended_data.get("predicted_funding", {}) if extended_data else {}
        funding_hist = extended_data.get("funding_history", {}) if extended_data else {}
        oi_analysis = extended_data.get("oi_analysis", {}) if extended_data else {}
        cascades = extended_data.get("liquidation_cascades", {}) if extended_data else {}
        whale_walls_data = extended_data.get("whale_walls", {}) if extended_data else {}

        funding_signals = analyze_funding_extremes(funding_data, pred_funding, funding_hist)
        oi_signals = analyze_oi_divergence(funding_data, oi_analysis, cascades)
        whale_signals = analyze_whale_walls(whale_walls_data, funding_data)

        # Vault signals (optional — may be slow)
        vault_signals = []
        try:
            vaults = fetch_vault_summaries()
            if vaults:
                vault_positions = {}
                for v in vaults[:3]:  # Top 3 vaults only
                    addr = v.get("vault_address", "")
                    if addr:
                        positions = fetch_vault_positions(addr)
                        if positions:
                            vault_positions[addr] = positions
                        time.sleep(0.2)
                vault_signals = analyze_vault_signals(vaults, vault_positions)
                if vault_signals:
                    print(f"[+] Vault signals: {len(vault_signals)} coins")
        except Exception as e:
            log.warning("Vault analysis failed: %s", e)

        # BTC-Neutral Mean Reversion signals
        btc_neutral_signals = []
        try:
            btc_candles = fetch_candles("BTC", interval="4h", limit=60)
            btc_prices = [c["close"] for c in btc_candles if "close" in c]
            if len(btc_prices) >= 30:
                for coin in TA_COINS:
                    try:
                        coin_candles = fetch_candles(coin, interval="4h", limit=60)
                        coin_prices = [c["close"] for c in coin_candles if "close" in c]
                        adx_info = ta_data.get(coin, {}).get("adx")
                        signals = analyze_btc_neutral(
                            coin, coin_prices, btc_prices, adx_info=adx_info
                        )
                        btc_neutral_signals.extend(signals)
                        if signals:
                            print(f"[+] BTC-Neutral {coin}: {signals[0]['signal']} Z={signals[0]['z_score']:+.2f}")
                        time.sleep(0.2)
                    except Exception as e:
                        log.warning("BTC-Neutral for %s failed: %s", coin, e)
        except Exception as e:
            log.warning("BTC-Neutral init failed: %s", e)

        combined = combine_strategies(
            funding_signals, oi_signals, whale_signals, vault_signals,
            confluence_data, ta_data,
            btc_neutral_signals=btc_neutral_signals,
        )
        combined = validate_signals(combined, ta_data)
        if combined:
            strategy_report = format_strategy_report(combined)
            for r in combined[:3]:
                print(f"    {r['coin']}: {r['recommendation']} (net: {r['net_score']:+d}) via {', '.join(r['strategies'])}")
    except Exception as e:
        log.warning("Strategy intelligence failed: %s", e)

    # Legacy RSI (from TA data)
    rsi_data = {}
    for coin in TA_COINS[:5]:
        if coin in ta_data and ta_data[coin].get("rsi") is not None:
            rsi_data[coin] = ta_data[coin]["rsi"]

    # 3. Проверяем SL/TP — автоматическое закрытие позиций
    print("[*] Проверяем SL/TP...")
    auto_closed = check_sl_tp(portfolio, prices, hl_market)
    if auto_closed:
        print(f"[!] Автоматически закрыто {len(auto_closed)} позиций по SL/TP")
        save_portfolio(portfolio)

    # 3a. Пересчёт сигналов для открытых позиций (выход по развороту / ослаблению)
    print("[*] Проверяем актуальность сигналов для открытых позиций...")
    signal_closed = check_signal_validity(portfolio, combined, prices, hl_market)
    if signal_closed:
        print(f"[!] Закрыто {len(signal_closed)} позиций по сигналу (reversal/expired)")
        save_portfolio(portfolio)
        auto_closed.extend(signal_closed)

    # 3b. P&L оставшихся позиций
    pnl_lines, total_value = calc_pnl(portfolio, prices, hl_market)

    # 3c. NewsAgent signal (if available)
    news_signal = None
    if _NEWS_AGENT_AVAILABLE and get_news_signal:
        try:
            news_signal = get_news_signal()
            if news_signal:
                print(f"[+] NewsAgent: sentiment={news_signal.get('overall_sentiment', '?')}")
        except Exception as e:
            log.warning("NewsAgent failed: %s", e)

    # 4. Промпт и анализ Claude — с ПОЛНЫМИ данными Hyperliquid
    print("[*] Строим промпт (Hyperliquid Extended + Multi-TF TA + Strategies + News)...")
    prompt = build_prompt(
        prices, news, fear_greed, btc_dom, total_mcap,
        portfolio, pnl_lines, total_value,
        rsi_data=rsi_data, hl_market=hl_market, ta_reports=ta_reports,
        strategy_report=strategy_report, extended_data=extended_data,
        news_signal=news_signal,
    )
    log.info("Prompt length: %d chars", len(prompt))

    print("[*] Спрашиваем Claude...")
    analysis_text = ask_claude(prompt)

    if not analysis_text:
        analysis_text = "⚠️ Claude не ответил. Данные получены, анализ недоступен."

    # 5. Парсим торговые решения
    print("[*] Парсим торговые решения...")
    actions = parse_trading_decisions(analysis_text, portfolio, prices)

    # 6. Исполняем сделки — с TA validation
    print("[*] Исполняем сделки (с TA валидацией)...")
    trade_log = auto_closed + execute_trades(actions, portfolio, prices, hl_market, ta_data, extended_data)

    # 7. Сохраняем портфель
    pnl_lines_final, total_value_final = calc_pnl(portfolio, prices, hl_market)
    total_pnl = total_value_final - portfolio["initial_capital"]

    # Определяем настроение рынка — из TA scores (объективнее чем из текста Claude)
    if ta_data:
        avg_score = sum(d.get("score", 0) for d in ta_data.values()) / len(ta_data)
        if avg_score > 20:
            sentiment = "bullish"
        elif avg_score < -20:
            sentiment = "bearish"
        else:
            sentiment = "neutral"
    else:
        analysis_lower = (analysis_text or "").lower()
        if any(w in analysis_lower for w in ["bullish", "бычий", "рост", "покупать"]):
            sentiment = "bullish"
        elif any(w in analysis_lower for w in ["bearish", "медвежий", "падение", "продавать"]):
            sentiment = "bearish"
        else:
            sentiment = "neutral"

    actions_count = sum(1 for t in trade_log if t.startswith("✅"))
    summary_text = ""
    for line in (analysis_text or "").split("\n"):
        if line.strip() and len(line.strip()) > 20:
            summary_text = line.strip()[:150]
            break

    # TA summary for history
    ta_summary = {}
    for coin, ta in ta_data.items():
        ta_summary[coin] = {
            "score": ta.get("score", 0),
            "rec": ta.get("recommendation", "?"),
            "rsi": ta.get("rsi"),
        }

    # Confluence summary for history
    conf_summary = {}
    for coin, conf in confluence_data.items():
        conf_summary[coin] = {
            "confluence": conf.get("confluence_score", 0),
            "direction": conf.get("direction", "?"),
            "weighted": conf.get("weighted_score", 0),
        }

    portfolio.setdefault("scan_history", []).append({
        "time": datetime.now().isoformat(),
        "total_value": round(total_value_final, 2),
        "portfolio_value": round(total_value_final, 2),
        "pnl": round(total_pnl, 2),
        "sentiment": sentiment,
        "actions_taken": actions_count,
        "summary": summary_text,
        "trades": trade_log,
        "ta_scores": ta_summary,
        "confluence": conf_summary,
        "data_source": "hyperliquid_extended" if extended_data else ("hyperliquid" if hl_market else "coingecko"),
    })
    portfolio["scan_history"] = portfolio["scan_history"][-50:]
    save_portfolio(portfolio)
    print("[*] Портфель сохранён")

    # 8. Лог
    hl_prices = {coin: info["price"] for coin, info in (hl_market or {}).items()}
    scan_result = {
        "time": datetime.now().isoformat(),
        "fear_greed": fear_greed,
        "btc_dom": btc_dom,
        "prices_hl": hl_prices,
        "prices_cg": {ASSET_SYMBOLS.get(k, k): v.get("usd") for k, v in prices.items()},
        "news_count": len(news),
        "analysis_len": len(analysis_text),
        "trades": trade_log,
        "portfolio_value": round(total_value_final, 2),
        "cash": portfolio["cash"],
        "ta_scores": ta_summary,
        "confluence": {c: {"score": d.get("confluence_score"), "dir": d.get("direction")} for c, d in confluence_data.items()},
        "extended_data_available": bool(extended_data),
    }
    save_log(scan_result)

    # 9. Пересчитываем P&L после сделок
    pnl_lines_final, total_value_final = calc_pnl(portfolio, prices, hl_market)

    # 10. Telegram — enhanced message
    print("[*] Отправляем в Telegram...")
    msg = format_telegram_message(analysis_text, trade_log, portfolio, prices, pnl_lines_final,
                                  total_value_final, fear_greed, btc_dom, hl_market, ta_data,
                                  confluence_data, extended_data)
    send_telegram(msg)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] === SCAN v3 COMPLETE ===")
    if trade_log:
        print("Сделки:")
        for t in trade_log:
            print(f"  {t}")

if __name__ == "__main__":
    main()
