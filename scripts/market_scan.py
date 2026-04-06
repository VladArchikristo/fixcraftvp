#!/usr/bin/env python3
"""
Market Scanner — запускается 3x в день (9:00 / 15:00 / 21:00)
Сканирует рынок, анализирует через Claude, обновляет paper portfolio.
"""

import json
import os
import sys
import subprocess
import tempfile
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# === CONFIG ===
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
ENV_FILE = PROJECT_DIR / "trading-bot" / ".env"
PORTFOLIO_FILE = PROJECT_DIR / "trading-bot" / "data" / "paper_portfolio.json"
LOG_FILE = Path.home() / "logs" / "cron" / "market-scan.log"
TOTAL_BUDGET = 100
MAX_POSITION_SIZE = 40

# Load token from .env
def _load_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("'\"")
    return env

_env = _load_env()
TELEGRAM_TOKEN = _env.get("VASILY_BOT_TOKEN", "")
CHAT_ID = "244710532"

COINS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "DOGE": "dogecoin",
    "ADA": "cardano",
    "AVAX": "avalanche-2",
    "MATIC": "matic-network",
    "DOT": "polkadot",
}


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def fetch_url(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def get_prices():
    ids = ",".join(COINS.values())
    url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={ids}&order=market_cap_desc&price_change_percentage=1h,24h,7d"
    try:
        data = fetch_url(url)
        result = {}
        for coin in data:
            symbol = coin["symbol"].upper()
            result[symbol] = {
                "price": coin["current_price"],
                "change_1h": coin.get("price_change_percentage_1h_in_currency", 0) or 0,
                "change_24h": coin.get("price_change_percentage_24h_in_currency", 0) or 0,
                "change_7d": coin.get("price_change_percentage_7d_in_currency", 0) or 0,
                "volume_24h": coin.get("total_volume", 0) or 0,
                "market_cap": coin.get("market_cap", 0) or 0,
            }
        return result
    except Exception as e:
        log(f"ERROR getting prices: {e}")
        return {}


def get_news():
    try:
        url = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN&categories=BTC,ETH,SOL&limit=15"
        data = fetch_url(url)
        news_items = []
        for item in data.get("Data", [])[:10]:
            news_items.append({
                "title": item.get("title", ""),
                "body": item.get("body", "")[:200],
                "tags": item.get("tags", ""),
                "published": datetime.fromtimestamp(item.get("published_on", 0)).strftime("%H:%M"),
            })
        return news_items
    except Exception as e:
        log(f"ERROR getting news: {e}")
        return []


def get_fear_greed():
    try:
        data = fetch_url("https://api.alternative.me/fng/?limit=1")
        item = data["data"][0]
        return {"value": int(item["value"]), "label": item["value_classification"]}
    except Exception as e:
        log(f"ERROR getting fear/greed: {e}")
        return {"value": 50, "label": "Neutral"}


def load_portfolio():
    try:
        data = json.loads(PORTFOLIO_FILE.read_text(encoding="utf-8"))
        # Ensure unified format
        data.setdefault("initial_capital", TOTAL_BUDGET)
        data.setdefault("cash", TOTAL_BUDGET)
        data.setdefault("positions", [])
        data.setdefault("closed_trades", [])
        data.setdefault("scan_history", [])
        # Normalize position field names (entry vs entry_price, direction vs side)
        for pos in data["positions"]:
            if "entry_price" in pos and "entry" not in pos:
                pos["entry"] = pos.pop("entry_price")
            if "side" in pos and "direction" not in pos:
                pos["direction"] = pos.pop("side")
            if "size_usd" not in pos:
                pos["size_usd"] = 0
        return data
    except Exception as e:
        log(f"ERROR loading portfolio: {e}")
        return {
            "initial_capital": TOTAL_BUDGET,
            "cash": TOTAL_BUDGET,
            "positions": [],
            "closed_trades": [],
            "scan_history": [],
        }


def save_portfolio(portfolio):
    portfolio["updated_at"] = datetime.now(timezone.utc).isoformat()
    # Keep only last 50 scan history entries
    portfolio["scan_history"] = portfolio.get("scan_history", [])[-50:]
    # Atomic write
    PORTFOLIO_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(
            dir=str(PORTFOLIO_FILE.parent), suffix=".tmp"
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(portfolio, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, str(PORTFOLIO_FILE))
        tmp_path = None
        log("Portfolio saved")
    except Exception as e:
        log(f"ERROR saving portfolio: {e}")
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def send_telegram(text):
    if not TELEGRAM_TOKEN:
        log("ERROR: no VASILY_BOT_TOKEN in .env")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = json.dumps({
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
        }).encode()
        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        log(f"Telegram error: {e}")
        # Retry without markdown
        try:
            payload = json.dumps({"chat_id": CHAT_ID, "text": text}).encode()
            req = urllib.request.Request(
                url, data=payload, headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass


def run_claude_analysis(market_data, news, fear_greed, portfolio):
    positions_text = ""
    for p in portfolio.get("positions", []):
        price = market_data.get(p["asset"], {}).get("price", 0)
        if price and p.get("entry"):
            pnl_pct = ((price - p["entry"]) / p["entry"]) * 100
            pnl_usd = (price - p["entry"]) / p["entry"] * p["size_usd"]
            positions_text += f"  - {p.get('direction','LONG')} {p['asset']}: вход ${p['entry']:.2f}, сейчас ${price:.2f}, PnL: {pnl_pct:+.2f}% (${pnl_usd:+.2f})\n"

    prices_text = ""
    for sym, d in sorted(market_data.items()):
        prices_text += f"  {sym}: ${d['price']:.4f} | 1h: {d['change_1h']:+.2f}% | 24h: {d['change_24h']:+.2f}% | 7d: {d['change_7d']:+.2f}%\n"

    news_text = ""
    for i, n in enumerate(news[:8], 1):
        news_text += f"  {i}. [{n['published']}] {n['title']}\n"

    prompt = f"""Ты Василий — опытный трейдер и криптоаналитик. Сейчас {datetime.now().strftime('%H:%M %d.%m.%Y')}.

ТЕКУЩИЙ РЫНОК:
{prices_text}

ИНДЕКС СТРАХА/ЖАДНОСТИ: {fear_greed['value']}/100 ({fear_greed['label']})

ПОСЛЕДНИЕ НОВОСТИ:
{news_text}

ТЕКУЩИЙ ПОРТФЕЛЬ (paper trading, ${TOTAL_BUDGET} начальный капитал):
Кэш: ${portfolio.get('cash', 0):.2f}
Открытые позиции:
{positions_text if positions_text else '  Нет позиций'}

ЗАДАЧА: Проведи объективный анализ рынка и прими торговые решения.

Правила:
- Максимум 3 позиции одновременно
- Максимум ${MAX_POSITION_SIZE} на одну позицию
- Торгуй только если есть чёткий сигнал
- Stop-loss ментально на -15% от входа
- Take profit частично на +20%, +40%
- При убытке позиции >15% — рассмотри закрытие

Ответь СТРОГО в формате JSON (только JSON, без пояснений):
{{
  "analysis": "краткий анализ рынка 2-3 предложения",
  "market_sentiment": "bullish|bearish|neutral",
  "actions": [
    {{
      "type": "OPEN|CLOSE|HOLD|NOOP",
      "asset": "BTC|ETH|SOL|...",
      "direction": "LONG|SHORT",
      "size_usd": 25,
      "reason": "причина в 1 предложении"
    }}
  ],
  "watchlist": ["список монет за которыми следим"],
  "risks": "главные риски сейчас"
}}

Если действий нет — action type NOOP. Будь объективным, не торгуй ради торговли."""

    try:
        result = subprocess.run(
            [
                str(Path.home() / ".local" / "bin" / "claude"),
                "--model", "claude-haiku-4-5",
                "--max-tokens", "1000",
                "-p",
                prompt,
            ],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "HOME": str(Path.home())},
        )
        output = result.stdout.strip()
        start = output.find("{")
        end = output.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(output[start:end])
        else:
            log(f"Claude output (no JSON): {output[:300]}")
            return None
    except subprocess.TimeoutExpired:
        log("Claude timeout")
        return None
    except Exception as e:
        log(f"Claude error: {e}")
        return None


def apply_actions(portfolio, actions, prices):
    changes = []
    now = datetime.now(timezone.utc).isoformat()

    for action in actions:
        action_type = action.get("type", "NOOP")
        asset = action.get("asset", "").upper()
        direction = action.get("direction", "LONG")
        size_usd = float(action.get("size_usd", 0))
        reason = action.get("reason", "")

        if action_type == "NOOP":
            continue

        current_price = prices.get(asset, {}).get("price")
        if not current_price and asset != "CASH":
            log(f"No price for {asset}, skipping")
            continue

        if action_type == "OPEN":
            if portfolio["cash"] < size_usd:
                changes.append(f"  Нет кэша для {asset}")
                continue
            existing = [p for p in portfolio["positions"] if p["asset"] == asset]
            if existing:
                changes.append(f"  Позиция {asset} уже открыта")
                continue
            if len(portfolio["positions"]) >= 3:
                changes.append("  Достигнут лимит позиций (3)")
                continue

            portfolio["cash"] -= size_usd
            portfolio["positions"].append({
                "asset": asset,
                "direction": direction,
                "size_usd": size_usd,
                "entry": current_price,
                "opened_at": now,
            })
            changes.append(
                f"ОТКРЫТ {direction} {asset} ${size_usd:.0f} @ ${current_price:.4f} | {reason}"
            )
            log(f"OPEN {direction} {asset} ${size_usd} @ {current_price}")

        elif action_type == "CLOSE":
            pos_list = [p for p in portfolio["positions"] if p["asset"] == asset]
            if not pos_list:
                continue
            for pos in pos_list:
                pnl_pct = ((current_price - pos["entry"]) / pos["entry"]) * 100
                pnl_usd = (current_price - pos["entry"]) / pos["entry"] * pos["size_usd"]
                closed_value = pos["size_usd"] + pnl_usd
                portfolio["cash"] += closed_value
                portfolio["positions"].remove(pos)
                portfolio["closed_trades"].append({
                    "asset": asset,
                    "direction": pos.get("direction", "LONG"),
                    "size_usd": pos["size_usd"],
                    "entry": pos["entry"],
                    "exit": current_price,
                    "pnl_pct": round(pnl_pct, 2),
                    "pnl_usd": round(pnl_usd, 2),
                    "opened_at": pos.get("opened_at", ""),
                    "closed_at": now,
                    "reason": reason,
                })
                changes.append(
                    f"ЗАКРЫТ {pos.get('direction','LONG')} {asset} @ ${current_price:.4f} | "
                    f"PnL: {pnl_pct:+.2f}% (${pnl_usd:+.2f}) | {reason}"
                )
                log(f"CLOSE {asset} @ {current_price}, PnL: {pnl_pct:+.2f}%")

        elif action_type == "HOLD":
            pos_list = [p for p in portfolio["positions"] if p["asset"] == asset]
            if pos_list:
                pos = pos_list[0]
                pnl_pct = ((current_price - pos["entry"]) / pos["entry"]) * 100
                changes.append(f"ДЕРЖИМ {pos.get('direction','LONG')} {asset} | PnL: {pnl_pct:+.2f}% | {reason}")

    return changes


def calculate_portfolio_value(portfolio, prices):
    total = portfolio.get("cash", 0)
    for pos in portfolio.get("positions", []):
        price = prices.get(pos["asset"], {}).get("price", 0)
        if price and pos.get("entry"):
            pnl = (price - pos["entry"]) / pos["entry"] * pos["size_usd"]
            total += pos["size_usd"] + pnl
        else:
            total += pos.get("size_usd", 0)
    return total


def main():
    log("=== MARKET SCAN START ===")
    scan_time = datetime.now().strftime("%H:%M %d.%m.%Y")

    if not TELEGRAM_TOKEN:
        log("ERROR: VASILY_BOT_TOKEN not found in .env")
        sys.exit(1)

    log("Fetching prices...")
    prices = get_prices()
    if not prices:
        send_telegram("Market Scan — не удалось получить данные о ценах")
        return

    log("Fetching news...")
    news = get_news()

    log("Fetching fear/greed...")
    fear_greed = get_fear_greed()

    portfolio = load_portfolio()

    log("Running Claude analysis...")
    analysis = run_claude_analysis(prices, news, fear_greed, portfolio)

    if not analysis:
        msg = f"Market Scan {scan_time}\n\nClaude анализ недоступен\n\n"
        for sym in ["BTC", "ETH", "SOL"]:
            if sym in prices:
                d = prices[sym]
                arrow = "+" if d["change_24h"] > 0 else ""
                msg += f"{sym}: ${d['price']:.2f} ({arrow}{d['change_24h']:.2f}%)\n"
        send_telegram(msg)
        return

    changes = apply_actions(portfolio, analysis.get("actions", []), prices)
    final_value = calculate_portfolio_value(portfolio, prices)
    total_pnl = final_value - TOTAL_BUDGET

    # Record scan in history
    portfolio.setdefault("scan_history", []).append({
        "time": datetime.now(timezone.utc).isoformat(),
        "sentiment": analysis.get("market_sentiment", "neutral"),
        "portfolio_value": round(final_value, 2),
        "pnl": round(total_pnl, 2),
        "actions_taken": len([a for a in analysis.get("actions", []) if a.get("type") not in ("NOOP", "HOLD")]),
        "summary": analysis.get("analysis", "")[:200],
    })

    save_portfolio(portfolio)

    # Build Telegram message
    sentiment_map = {"bullish": "Bull", "bearish": "Bear", "neutral": "Neutral"}
    sentiment = analysis.get("market_sentiment", "neutral")

    msg = f"СКАН ВАСИЛИЯ {scan_time}\n"
    msg += f"Сентимент: {sentiment_map.get(sentiment, sentiment).upper()}\n"
    msg += f"Fear&Greed: {fear_greed['value']}/100 ({fear_greed['label']})\n\n"

    msg += "ЦЕНЫ:\n"
    for sym in ["BTC", "ETH", "SOL", "BNB", "XRP"]:
        if sym in prices:
            d = prices[sym]
            arrow = "+" if d["change_24h"] > 0 else ""
            msg += f"  {sym}: ${d['price']:,.2f} ({arrow}{d['change_24h']:.2f}%)\n"

    msg += f"\nАНАЛИЗ:\n{analysis.get('analysis', '')}\n"

    if changes:
        msg += "\nДЕЙСТВИЯ:\n"
        for c in changes:
            msg += f"  {c}\n"

    msg += "\nПОРТФЕЛЬ:\n"
    msg += f"  Кэш: ${portfolio.get('cash', 0):.2f}\n"
    for pos in portfolio.get("positions", []):
        price = prices.get(pos["asset"], {}).get("price", 0)
        if price and pos.get("entry"):
            pnl_pct = ((price - pos["entry"]) / pos["entry"]) * 100
            msg += f"  {pos.get('direction','LONG')} {pos['asset']}: {pnl_pct:+.2f}%\n"

    pnl_sign = "+" if total_pnl >= 0 else ""
    msg += f"  Итог: ${final_value:.2f} (старт ${TOTAL_BUDGET}, PnL: {pnl_sign}{total_pnl:.2f}$)\n"

    if analysis.get("risks"):
        msg += f"\nРИСКИ: {analysis['risks']}"

    send_telegram(msg)
    log(f"=== SCAN DONE | Portfolio: ${final_value:.2f} | PnL: {total_pnl:+.2f} ===")


if __name__ == "__main__":
    main()
