#!/usr/bin/env python3
"""
Василий Market Scanner — 3x Daily
Сканирует крипторынок, делает анализ через Claude CLI, обновляет paper portfolio.
"""

import json
import re
import subprocess
import sys
import os
import time
import logging
from logging.handlers import RotatingFileHandler
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from dotenv import load_dotenv

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

ASSETS = ["bitcoin", "ethereum", "solana", "binancecoin", "ripple",
          "cardano", "avalanche-2", "polkadot", "chainlink", "uniswap"]

ASSET_SYMBOLS = {
    "bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL",
    "binancecoin": "BNB", "ripple": "XRP", "cardano": "ADA",
    "avalanche-2": "AVAX", "polkadot": "DOT", "chainlink": "LINK", "uniswap": "UNI"
}

# ─── Портфель ─────────────────────────────────────────────────────────────────
def load_portfolio():
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
    try:
        with open(PORTFOLIO_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[ERROR] Portfolio file corrupted: {e}")
        backup = PORTFOLIO_FILE.with_suffix(".json.bak")
        PORTFOLIO_FILE.rename(backup)
        print(f"[WARN] Backed up corrupted portfolio to {backup}")
        return load_portfolio()

def save_portfolio(portfolio):
    """Save portfolio atomically (write to tmp → rename) to prevent corruption."""
    import tempfile
    portfolio["updated_at"] = datetime.now().isoformat()
    tmp_path = None
    try:
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

# ─── Рыночные данные ──────────────────────────────────────────────────────────
def fetch_prices():
    ids = ",".join(ASSETS)
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true&include_market_cap=true&include_24hr_vol=true"
    try:
        r = requests.get(url, timeout=15)
        return r.json()
    except Exception as e:
        print(f"[ERROR] fetch_prices: {e}")
        return {}

def fetch_fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        data = r.json()
        d = data["data"][0]
        return f"{d['value']} ({d['value_classification']})"
    except:
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

def fetch_btc_dominance():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=10)
        data = r.json()
        btc_dom = data["data"]["market_cap_percentage"].get("btc", 0)
        total_mcap = data["data"]["total_market_cap"].get("usd", 0)
        return round(btc_dom, 1), round(total_mcap / 1e12, 2)
    except:
        return "N/A", "N/A"

# ─── P&L расчёт + автоматическое закрытие по SL/TP ───────────────────────────
def check_sl_tp(portfolio, prices):
    """Проверяем SL/TP для всех позиций. Автоматически закрываем сработавшие."""
    auto_closed = []
    remaining = []
    now = datetime.now().isoformat()

    for pos in portfolio["positions"]:
        asset = pos["asset"]
        cg_id = next((k for k, v in ASSET_SYMBOLS.items() if v == asset), None)
        if not cg_id or cg_id not in prices:
            remaining.append(pos)
            continue

        cur_price = prices[cg_id]["usd"]
        entry = pos.get("entry_price", 0)
        if entry <= 0:
            log.warning("Позиция %s имеет entry_price=0, пропускаем", asset)
            remaining.append(pos)
            continue

        size_usd = pos["size_usd"]
        sl = pos.get("stop_loss")
        tp = pos.get("take_profit")
        side = pos.get("side", "LONG").upper()

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
            pnl_usd = cur_value - size_usd
            pnl_pct = (pnl_usd / size_usd) * 100

            portfolio["cash"] += cur_value
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


def calc_pnl(portfolio, prices):
    pnl_lines = []
    total_value = portfolio["cash"]

    for pos in portfolio["positions"]:
        asset = pos["asset"]
        cg_id = next((k for k, v in ASSET_SYMBOLS.items() if v == asset), None)
        if not cg_id or cg_id not in prices:
            continue

        cur_price = prices[cg_id]["usd"]
        entry = pos.get("entry_price", 0)
        size_usd = pos.get("size_usd", 0)

        if entry <= 0 or size_usd <= 0:
            log.warning("Позиция %s: некорректные данные (entry=%.2f, size=%.2f)", asset, entry, size_usd)
            continue

        qty = size_usd / entry
        cur_value = qty * cur_price
        pnl_usd = cur_value - size_usd
        pnl_pct = (pnl_usd / size_usd) * 100

        sl = pos.get("stop_loss")
        tp = pos.get("take_profit")
        sl_tp_info = f" | SL:${sl:.2f} TP:${tp:.2f}" if sl and tp else " | ⚠️ БЕЗ SL/TP"

        total_value += cur_value
        pnl_lines.append(
            f"  {pos.get('side','LONG')} {asset}: вход ${entry:.2f} → сейчас ${cur_price:.2f} | "
            f"P&L: {'+' if pnl_usd >= 0 else ''}{pnl_usd:.2f}$ ({'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%){sl_tp_info}"
        )

    return pnl_lines, total_value

# ─── Сборка промпта для Claude ─────────────────────────────────────────────────
def build_prompt(prices, news, fear_greed, btc_dom, total_mcap, portfolio, pnl_lines, total_value):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Цены топ активов
    price_block = ""
    for cg_id, sym in ASSET_SYMBOLS.items():
        if cg_id in prices:
            p = prices[cg_id]
            ch = p.get("usd_24h_change", 0) or 0
            vol = p.get("usd_24h_vol", 0) or 0
            price_block += f"  {sym}: ${p['usd']:,.2f} | 24h: {'+' if ch >= 0 else ''}{ch:.1f}% | Vol: ${vol/1e6:.0f}M\n"

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

    prompt = f"""Ты Василий — опытный крипто-трейдер. Сейчас {now} UTC.

═══════════════ РЫНОЧНЫЕ ДАННЫЕ ═══════════════
ЦЕНЫ И ОБЪЁМЫ (топ-10):
{price_block}
Fear & Greed Index: {fear_greed}
BTC Dominance: {btc_dom}%
Total Market Cap: ${total_mcap}T

═══════════════ НОВОСТИ (последние 8ч) ═══════════════
{news_block}
═══════════════ ТЕКУЩИЙ ПОРТФЕЛЬ ═══════════════
Кэш: ${portfolio['cash']:.2f}
Начальный капитал: ${portfolio['initial_capital']:.2f}
Открытые позиции:
{pos_block}

Общая стоимость портфеля: ~${total_value:.2f}
Общий P&L: {'+' if total_value >= portfolio['initial_capital'] else ''}{total_value - portfolio['initial_capital']:.2f}$ ({'+' if total_value >= portfolio['initial_capital'] else ''}{((total_value/portfolio['initial_capital'])-1)*100:.1f}%)

═══════════════ ЗАДАЧА ═══════════════
Сделай ПОЛНЫЙ объективный анализ:

1. НАСТРОЕНИЕ РЫНКА — bull/bear/neutral и почему, оценка рисков
2. АНАЛИЗ ПО КАЖДОМУ АКТИВУ — BTC, ETH, SOL + топ альты: тренд, уровни, риски
3. НОВОСТНОЙ ФОНД — что важно, что bullish/bearish
4. АНАЛИЗ ТЕКУЩИХ ПОЗИЦИЙ — оценить держать/закрыть/увеличить

5. ТОРГОВЫЕ РЕШЕНИЯ — ОБЯЗАТЕЛЬНЫЙ БЛОК:
Формат строго:
OPEN_POSITION: {{asset: "XXX", side: "LONG/SHORT", size_usd: NN, stop_loss: ЦЕНА, take_profit: ЦЕНА, reason: "..."}}
CLOSE_POSITION: {{asset: "XXX", reason: "..."}}
HOLD: {{asset: "XXX", reason: "..."}}
NO_ACTION: {{reason: "..."}}

ОБЯЗАТЕЛЬНО указывай stop_loss и take_profit в каждом OPEN_POSITION!
Определяй TP по стратегии: уровни сопротивления, волатильность актива, тренд. TP может быть 5%, 15%, 30%+ — решай по ситуации.
SL ставь по ближайшему уровню поддержки или 3-7% от входа.

Важно: кэш доступен ${portfolio['cash']:.2f}. Максимум на позицию — 30% от кэша. Не открывать позиции если кэш < $10.
Доступные активы: {', '.join(available_syms)}

6. ПРОГНОЗ на 24-48 часов по портфелю

Будь объективен. Называй риски. Не давай пустых советов."""

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
                try:
                    return json.loads(text[start:i + 1])
                except (json.JSONDecodeError, ValueError):
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


def _try_parse_json(text: str):
    """Пытаемся извлечь JSON из строки, поддерживая разные форматы Claude."""
    text = text.strip()
    # Прямой парсинг
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass
    # Поиск JSON внутри строки через regex
    match = _JSON_RE.search(text)
    if match:
        try:
            return json.loads(match.group())
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

def execute_trades(actions, portfolio, prices):
    """Применяем торговые решения к бумажному портфелю"""
    trade_log = []
    now = datetime.now().isoformat()

    for action_type, data in actions:
        if action_type == "OPEN":
            asset = data.get("asset", "").upper()
            side = data.get("side", "LONG").upper()
            size_usd = float(data.get("size_usd", 0))
            reason = data.get("reason", "")

            # Проверки
            if size_usd <= 0 or size_usd > portfolio["cash"]:
                trade_log.append(f"❌ OPEN {asset}: недостаточно кэша (нужно ${size_usd:.0f}, есть ${portfolio['cash']:.0f})")
                continue

            # Лимит 30% на позицию
            max_position = portfolio["cash"] * 0.30
            if size_usd > max_position:
                log.warning("OPEN %s: size_usd $%.0f превышает 30%% лимит $%.0f, обрезаем", asset, size_usd, max_position)
                size_usd = round(max_position, 2)

            # Найти цену
            cg_id = next((k for k, v in ASSET_SYMBOLS.items() if v == asset), None)
            if not cg_id or cg_id not in prices:
                trade_log.append(f"❌ OPEN {asset}: цена не найдена")
                continue

            cur_price = prices[cg_id]["usd"]

            # SL/TP — берём из данных Claude или адаптивные по волатильности
            sl = data.get("stop_loss")
            tp = data.get("take_profit")
            if not sl or not tp:
                vol_24h = abs(prices[cg_id].get("usd_24h_change", 5) or 5)
                sl_pct = max(0.03, min(vol_24h / 100 * 1.5, 0.10))  # 3-10% от волатильности
                tp_pct = max(0.05, min(vol_24h / 100 * 3.0, 0.30))  # 5-30%, R:R ~2:1
                if not sl:
                    sl = cur_price * ((1 - sl_pct) if side == "LONG" else (1 + sl_pct))
                if not tp:
                    tp = cur_price * ((1 + tp_pct) if side == "LONG" else (1 - tp_pct))

            # Открываем позицию
            portfolio["cash"] -= size_usd
            portfolio["positions"].append({
                "asset": asset,
                "side": side,
                "size_usd": size_usd,
                "entry_price": cur_price,
                "stop_loss": round(float(sl), 2),
                "take_profit": round(float(tp), 2),
                "opened_at": now
            })
            trade_log.append(f"✅ ОТКРЫТА {side} {asset} ${size_usd:.0f} @ ${cur_price:.2f} SL:${sl:.2f} TP:${tp:.2f} | {reason}")

        elif action_type == "CLOSE":
            asset = data.get("asset", "").upper()
            reason = data.get("reason", "")

            # Найти позицию
            pos = next((p for p in portfolio["positions"] if p["asset"] == asset), None)
            if not pos:
                trade_log.append(f"❌ CLOSE {asset}: позиция не найдена")
                continue

            # Найти текущую цену
            cg_id = next((k for k, v in ASSET_SYMBOLS.items() if v == asset), None)
            if not cg_id or cg_id not in prices:
                trade_log.append(f"❌ CLOSE {asset}: цена не найдена")
                continue

            cur_price = prices[cg_id]["usd"]
            entry = pos.get("entry_price", 0)
            size_usd = pos.get("size_usd", 0)
            if entry <= 0 or size_usd <= 0:
                trade_log.append(f"❌ CLOSE {asset}: некорректные данные позиции")
                continue
            qty = size_usd / entry
            cur_value = qty * cur_price
            pnl_usd = cur_value - size_usd
            pnl_pct = (pnl_usd / size_usd) * 100

            # Закрываем
            portfolio["cash"] += cur_value
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
def ask_claude(prompt):
    """Вызываем Claude через CLI"""
    try:
        result = subprocess.run(
            [CLAUDE_PATH, "-p", prompt, "--model", "claude-haiku-4-5", "--output-format", "text"],
            capture_output=True, text=True, timeout=120,
            cwd="/Users/vladimirprihodko/Папка тест/fixcraftvp"
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            log.error("Claude stderr: %s", result.stderr[:500])
            return None
    except subprocess.TimeoutExpired:
        log.error("Claude timeout после 120 сек")
        return None
    except Exception as e:
        log.error("ask_claude error: %s", e)
        return None

# ─── Telegram ─────────────────────────────────────────────────────────────────
def send_telegram(text, max_len=4000):
    """Отправка в Telegram с retry (разбиваем длинные сообщения)."""
    chunks = [text[i:i+max_len] for i in range(0, len(text), max_len)]
    for i, chunk in enumerate(chunks):
        sent = False
        for attempt in range(3):
            try:
                resp = requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": CHAT_ID, "text": chunk, "parse_mode": "HTML"},
                    timeout=15
                )
                if resp.status_code == 200:
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
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    log_file = LOG_DIR / f"scan_{ts}.json"
    with open(log_file, "w") as f:
        json.dump(scan_result, f, indent=2, ensure_ascii=False)

    # Чистим старые логи — оставляем последние 30
    logs = sorted(LOG_DIR.glob("scan_*.json"))
    for old in logs[:-30]:
        old.unlink()

# ─── Форматирование Telegram сообщения ────────────────────────────────────────
def format_telegram_message(analysis, trade_log, portfolio, prices, pnl_lines, total_value, fear_greed, btc_dom):
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    # Сокращаем анализ до 2500 символов для Telegram
    analysis_short = analysis[:2500] + "..." if len(analysis) > 2500 else analysis

    trades_text = "\n".join(trade_log) if trade_log else "Действий не выполнено"
    pnl_text = "\n".join(pnl_lines) if pnl_lines else "Нет открытых позиций"

    pnl_total = total_value - portfolio["initial_capital"]
    pnl_pct = ((total_value / portfolio["initial_capital"]) - 1) * 100
    pnl_emoji = "📈" if pnl_total >= 0 else "📉"

    # Ключевые цены
    prices_mini = ""
    for cg_id, sym in [("bitcoin","BTC"),("ethereum","ETH"),("solana","SOL")]:
        if cg_id in prices:
            ch = prices[cg_id].get("usd_24h_change", 0) or 0
            prices_mini += f"{sym} ${prices[cg_id]['usd']:,.0f} ({'+' if ch >= 0 else ''}{ch:.1f}%)\n"

    msg = f"""🤖 <b>ВАСИЛИЙ MARKET SCAN</b> — {now}

💰 <b>Цены:</b>
{prices_mini}
😱 Fear&Greed: {fear_greed} | BTC Dom: {btc_dom}%

{pnl_emoji} <b>Портфель:</b>
{pnl_text}
Кэш: ${portfolio['cash']:.2f}
Итого: ${total_value:.2f} | P&L: {'+' if pnl_total >= 0 else ''}{pnl_total:.2f}$ ({'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%)

🔄 <b>Сделки:</b>
{trades_text}

📊 <b>Анализ Василия:</b>
{analysis_short}"""

    return msg

# ─── Главная функция ───────────────────────────────────────────────────────────
def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] === VASILY MARKET SCAN STARTED ===")

    # 1. Загружаем портфель
    portfolio = load_portfolio()
    print("[*] Портфель загружен")

    # 2. Рыночные данные
    print("[*] Получаем цены...")
    prices = fetch_prices()
    if not prices:
        send_telegram("❌ Василий: не удалось получить рыночные данные. Скан отменён.")
        sys.exit(1)

    print("[*] Fear & Greed...")
    fear_greed = fetch_fear_greed()

    print("[*] Новости...")
    news = fetch_news()

    print("[*] BTC dominance...")
    btc_dom, total_mcap = fetch_btc_dominance()

    # 3. Проверяем SL/TP — автоматическое закрытие позиций
    print("[*] Проверяем SL/TP...")
    auto_closed = check_sl_tp(portfolio, prices)
    if auto_closed:
        print(f"[!] Автоматически закрыто {len(auto_closed)} позиций по SL/TP")
        save_portfolio(portfolio)

    # 3b. P&L оставшихся позиций
    pnl_lines, total_value = calc_pnl(portfolio, prices)

    # 4. Промпт и анализ Claude
    print("[*] Строим промпт...")
    prompt = build_prompt(prices, news, fear_greed, btc_dom, total_mcap, portfolio, pnl_lines, total_value)

    print("[*] Спрашиваем Claude...")
    analysis = ask_claude(prompt)

    if not analysis:
        analysis = "⚠️ Claude не ответил. Данные получены, анализ недоступен."

    # 5. Парсим торговые решения
    print("[*] Парсим торговые решения...")
    actions = parse_trading_decisions(analysis, portfolio, prices)

    # 6. Исполняем сделки
    print("[*] Исполняем сделки...")
    trade_log = auto_closed + execute_trades(actions, portfolio, prices)

    # 7. Сохраняем портфель
    # Пересчитываем финальный P&L и детали для истории
    pnl_lines_final, total_value_final = calc_pnl(portfolio, prices)
    total_pnl = total_value_final - portfolio["initial_capital"]

    # Определяем настроение рынка из анализа
    analysis_lower = (analysis or "").lower()
    if any(w in analysis_lower for w in ["bullish", "бычий", "рост", "покупать"]):
        sentiment = "bullish"
    elif any(w in analysis_lower for w in ["bearish", "медвежий", "падение", "продавать"]):
        sentiment = "bearish"
    else:
        sentiment = "neutral"

    actions_count = sum(1 for t in trade_log if t.startswith("✅"))
    summary_text = ""
    for line in (analysis or "").split("\n"):
        if line.strip() and len(line.strip()) > 20:
            summary_text = line.strip()[:150]
            break

    portfolio.setdefault("scan_history", []).append({
        "time": datetime.now().isoformat(),
        "total_value": round(total_value_final, 2),
        "portfolio_value": round(total_value_final, 2),
        "pnl": round(total_pnl, 2),
        "sentiment": sentiment,
        "actions_taken": actions_count,
        "summary": summary_text,
        "trades": trade_log
    })
    # Оставляем последние 50 записей истории
    portfolio["scan_history"] = portfolio["scan_history"][-50:]
    save_portfolio(portfolio)
    print("[*] Портфель сохранён")

    # 8. Лог
    scan_result = {
        "time": datetime.now().isoformat(),
        "fear_greed": fear_greed,
        "btc_dom": btc_dom,
        "prices": {ASSET_SYMBOLS.get(k,k): v.get("usd") for k,v in prices.items()},
        "news_count": len(news),
        "analysis_len": len(analysis),
        "trades": trade_log,
        "portfolio_value": round(total_value, 2),
        "cash": portfolio["cash"]
    }
    save_log(scan_result)

    # 9. Пересчитываем P&L после сделок (портфель изменился)
    pnl_lines_final, total_value_final = calc_pnl(portfolio, prices)

    # 10. Telegram
    print("[*] Отправляем в Telegram...")
    msg = format_telegram_message(analysis, trade_log, portfolio, prices, pnl_lines_final, total_value_final, fear_greed, btc_dom)
    send_telegram(msg)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] === SCAN COMPLETE ===")
    if trade_log:
        print("Сделки:")
        for t in trade_log:
            print(f"  {t}")

if __name__ == "__main__":
    main()
