#!/usr/bin/env python3
"""
NewsAgent — внутренний суб-агент Василия для анализа новостного сентимента.

Собирает данные из:
- Fear & Greed Index (alternative.me)
- RSS feeds (CoinDesk, Cointelegraph, Decrypt)
- DeFi Llama /hacks (взломы и инциденты)
- CoinGecko trending (hot монеты)

Выдаёт JSON-сигнал с sentiment score (-1.0 ... +1.0), ключевыми событиями,
затронутыми активами и уровнем риска.

Кэширует результат в data/news_signal.json (TTL 15 мин).
"""

import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional

import requests

log = logging.getLogger("news_agent")

SCRIPT_DIR = Path(__file__).resolve().parent
CACHE_FILE = SCRIPT_DIR / "data" / "news_signal.json"
CACHE_TTL_SECONDS = 15 * 60  # 15 минут

# ─── Ключевые слова для сентимента ────────────────────────────────────────────
BEARISH_KEYWORDS = [
    "hack", "exploit", "breach", "stolen", "rugpull", "rug pull", "scam", "fraud",
    "ban", "banned", "prohibit", "crackdown", "sec", "lawsuit", "investigation",
    "crash", "collapse", "liquidat", "bankrupt", "insolvency", "insolvent",
    "sanction", "arrest", "seized", "shutdown", "suspend", "freeze",
    "manipulation", "ponzi", "bubble", "dump", "dumping",
    "взлом", "запрет", "обвал", "мошенничество",
]

BULLISH_KEYWORDS = [
    "etf", "approval", "approved", "launch", "partnership", "adoption",
    "listing", "listed", "upgrade", "protocol", "integration",
    "institutional", "investment", "bull", "breakout", "ath",
    "all-time high", "record", "milestone", "breakthrough",
    "легализация", "одобрение", "листинг",
]

HIGH_RISK_KEYWORDS = [
    "hack", "exploit", "stolen", "millions", "billion", "crash", "collapse",
    "ban", "sec action", "emergency", "halt", "suspend", "bankrupt",
    "rugpull", "rug pull", "fraud", "ponzi",
]

# Коины которые нас интересуют
TRACKED_ASSETS = [
    "BTC", "ETH", "SOL", "XRP", "AVAX", "DOGE", "MATIC", "BNB",
    "ADA", "DOT", "INJ", "UNI", "ARB", "OP", "LINK", "ATOM",
]


def _load_cache() -> Optional[dict]:
    """Читаем кэш. Возвращает None если устарел или не существует."""
    if not CACHE_FILE.exists():
        return None
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        cached_at = data.get("cached_at", 0)
        if time.time() - cached_at < CACHE_TTL_SECONDS:
            return data
    except Exception:
        pass
    return None


def _save_cache(signal: dict):
    """Сохраняем сигнал в кэш."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    signal["cached_at"] = time.time()
    try:
        CACHE_FILE.write_text(json.dumps(signal, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        log.warning("Не удалось сохранить кэш: %s", e)


def fetch_fear_greed() -> dict:
    """Fear & Greed Index: 0 (Extreme Fear) → 100 (Extreme Greed)."""
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=2", timeout=10)
        data = r.json()["data"]
        current = data[0]
        prev = data[1] if len(data) > 1 else current
        val = int(current["value"])
        prev_val = int(prev["value"])
        return {
            "value": val,
            "label": current["value_classification"],
            "previous": prev_val,
            "trend": "rising" if val > prev_val else ("falling" if val < prev_val else "stable"),
        }
    except Exception as e:
        log.warning("fear_greed failed: %s", e)
        return {"value": 50, "label": "Neutral", "previous": 50, "trend": "stable"}


def fetch_rss_news() -> list[dict]:
    """Новости из RSS лент за последние 12 часов."""
    RSS_FEEDS = [
        ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
        ("Cointelegraph", "https://cointelegraph.com/rss"),
        ("Decrypt", "https://decrypt.co/feed"),
        ("The Block", "https://www.theblock.co/rss.xml"),
    ]
    headers = {"User-Agent": "Mozilla/5.0 (compatible; VasilyNewsAgent/1.0)"}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=12)
    news = []

    for source, url in RSS_FEEDS:
        try:
            r = requests.get(url, timeout=15, headers=headers)
            root = ET.fromstring(r.text)
            channel = root.find("channel")
            if channel is None:
                continue
            for item in channel.findall("item")[:15]:
                title = item.findtext("title", "").strip()
                desc = re.sub(r"<[^>]+>", "", item.findtext("description", ""))[:300].strip()
                pub = item.findtext("pubDate", "")
                ts = None
                try:
                    dt = parsedate_to_datetime(pub)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt < cutoff:
                        continue
                    ts = dt.isoformat()
                except Exception:
                    pass
                if title:
                    news.append({"title": title, "body": desc, "source": source, "ts": ts})
        except Exception as e:
            log.warning("RSS %s: %s", source, e)

    return news[:20]


def fetch_defi_llama_hacks() -> list[dict]:
    """
    Security RSS feeds — хаки, взломы и инциденты за последние 72 часа.

    Источники:
    - Chainalysis blog RSS (https://www.chainalysis.com/feed/)
    - SlowMist Medium RSS (https://slowmist.medium.com/feed)

    Примечание: DeFi Llama /hacks перешёл на платный план (paywall),
    домен llama.fi не резолвится. Заменено на специализированные security RSS.
    """
    SECURITY_FEEDS = [
        ("Chainalysis", "https://www.chainalysis.com/feed/"),
        ("SlowMist", "https://slowmist.medium.com/feed"),
    ]
    HACK_KEYWORDS = [
        "hack", "exploit", "breach", "stolen", "rugpull", "rug pull",
        "phishing", "drained", "attack", "compromise", "theft", "heist",
        "vulnerability", "flash loan", "flashloan",
    ]
    # Извлечение суммы из заголовка: $285 Million, $10M, $1.5B
    AMOUNT_RE = re.compile(r"\$\s*(\d+(?:\.\d+)?)\s*(M|B|K|Million|Billion|Thousand)?", re.IGNORECASE)

    headers = {"User-Agent": "Mozilla/5.0 (compatible; VasilyNewsAgent/1.0)"}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=72)
    incidents = []

    for source, url in SECURITY_FEEDS:
        try:
            r = requests.get(url, timeout=15, headers=headers)
            root = ET.fromstring(r.text)
            channel = root.find("channel")
            if channel is None:
                continue
            for item in channel.findall("item")[:20]:
                # Очищаем CDATA если есть
                raw_title = item.findtext("title", "")
                title = re.sub(r"<!\[CDATA\[|\]\]>", "", raw_title).strip()
                if not title:
                    continue
                title_lower = title.lower()
                if not any(kw in title_lower for kw in HACK_KEYWORDS):
                    continue

                # Проверяем свежесть
                pub = item.findtext("pubDate", "")
                try:
                    dt = parsedate_to_datetime(pub)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt < cutoff:
                        continue
                except Exception:
                    pass  # Если дата не парсится — включаем статью

                # Пытаемся извлечь сумму ущерба
                amount = 0.0
                m = AMOUNT_RE.search(title)
                if m:
                    val = float(m.group(1))
                    unit = (m.group(2) or "").upper()
                    if unit in ("B", "BILLION"):
                        amount = val * 1e9
                    elif unit in ("M", "MILLION"):
                        amount = val * 1e6
                    elif unit in ("K", "THOUSAND"):
                        amount = val * 1e3
                    else:
                        amount = val * 1e6  # без единицы — считаем миллионами

                # Короткое имя до двоеточия или первые 60 символов
                name = title.split(":")[0].strip() if ":" in title else title[:60]
                amount_str = f": ${amount / 1e6:.1f}M stolen" if amount > 0 else ""
                incidents.append({
                    "title": f"[HACK] {name}{amount_str}",
                    "body": title,
                    "source": source,
                    "severity": "HIGH" if amount > 1e6 else "MEDIUM",
                })
        except Exception as e:
            log.warning("security_feed %s: %s", source, e)

    return incidents[:5]


def fetch_coingecko_trending() -> list[str]:
    """CoinGecko trending монеты (топ-7 поисков за 24ч) — без API ключа."""
    try:
        r = requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=15)
        data = r.json()
        coins = [c["item"]["symbol"].upper() for c in data.get("coins", [])[:7]]
        return coins
    except Exception as e:
        log.warning("coingecko_trending failed: %s", e)
        return []


def _score_news(news_items: list[dict], fg_value: int, hacks: list[dict]) -> float:
    """
    Вычисляем сентимент скор от -1.0 до +1.0.

    Логика:
    - Fear & Greed → базовый скор (0–100 → -1.0 … +1.0)
    - Bearish keywords в заголовках → -0.05 за каждый (макс -0.3)
    - Bullish keywords → +0.05 за каждый (макс +0.3)
    - Каждый hack/exploit из DeFi Llama → -0.15
    """
    # Fear & Greed: 50 = neutral (score 0), 100 = +1.0, 0 = -1.0
    base = (fg_value - 50) / 50.0

    news_delta = 0.0
    full_text = " ".join(
        (n.get("title", "") + " " + n.get("body", "")).lower()
        for n in news_items
    )

    bearish_hits = sum(1 for kw in BEARISH_KEYWORDS if kw in full_text)
    bullish_hits = sum(1 for kw in BULLISH_KEYWORDS if kw in full_text)

    news_delta += min(bullish_hits * 0.04, 0.3)
    news_delta -= min(bearish_hits * 0.04, 0.3)

    # Хаки — всегда bearish
    news_delta -= len(hacks) * 0.15

    raw = base + news_delta
    return max(-1.0, min(1.0, round(raw, 3)))


def _extract_affected_assets(news_items: list[dict]) -> list[str]:
    """Ищем упоминания трекируемых активов в новостях."""
    full_text = " ".join(
        (n.get("title", "") + " " + n.get("body", "")).upper()
        for n in news_items
    )
    return [a for a in TRACKED_ASSETS if a in full_text]


def _risk_level(score: float, hacks: list[dict], fg_value: int) -> str:
    """Определяем риск-уровень: LOW / MEDIUM / HIGH / CRITICAL."""
    if hacks or score < -0.6 or fg_value < 20:
        return "CRITICAL"
    if score < -0.3 or fg_value < 35:
        return "HIGH"
    if abs(score) < 0.2 and 40 < fg_value < 60:
        return "LOW"
    return "MEDIUM"


def _key_events(news_items: list[dict], hacks: list[dict]) -> list[str]:
    """Топ-5 ключевых событий для Васи."""
    events = []
    # Сначала хаки — они самые важные
    for h in hacks[:2]:
        events.append(h["title"])
    # Потом новости с high-risk словами
    for n in news_items:
        title = n["title"]
        title_lower = title.lower()
        if any(kw in title_lower for kw in HIGH_RISK_KEYWORDS):
            if title not in events:
                events.append(title)
            if len(events) >= 5:
                break
    # Добираем обычными новостями
    for n in news_items:
        if len(events) >= 5:
            break
        if n["title"] not in events:
            events.append(n["title"])
    return events[:5]


def _sentiment_label(score: float) -> str:
    if score >= 0.5:
        return "bullish"
    if score >= 0.2:
        return "slightly_bullish"
    if score > -0.2:
        return "neutral"
    if score > -0.5:
        return "slightly_bearish"
    return "bearish"


def _vasily_action(score: float, risk: str) -> str:
    """Рекомендация для Васи как реагировать на текущий новостной фон."""
    if risk == "CRITICAL":
        return "STOP_NEW_ENTRIES — критический риск, только защита существующих позиций"
    if risk == "HIGH":
        return "REDUCE_SIZE — уменьши размер новых позиций на 50%, ужесточи SL"
    if score >= 0.4 and risk == "LOW":
        return "FULL_SIZE — позитивный фон, можно торговать полными размерами"
    if score <= -0.3:
        return "DEFENSIVE — преимущество защитных позиций, избегай агрессивных LONG"
    return "NORMAL — стандартное управление рисками"


def get_news_signal(force_refresh: bool = False) -> dict:
    """
    Главная функция. Возвращает структурированный новостной сигнал для Васи.

    Использует кэш если данные свежие (< 15 мин), иначе обновляет.
    """
    if not force_refresh:
        cached = _load_cache()
        if cached:
            log.info("NewsAgent: returning cached signal (age %.1f min)",
                     (time.time() - cached["cached_at"]) / 60)
            return cached

    log.info("NewsAgent: fetching fresh data...")
    start = time.time()

    # Параллельный сбор (последовательно — проще, без threadpool)
    fg = fetch_fear_greed()
    rss_news = fetch_rss_news()
    hacks = fetch_defi_llama_hacks()
    trending = fetch_coingecko_trending()

    all_items = rss_news + hacks
    score = _score_news(all_items, fg["value"], hacks)
    affected = _extract_affected_assets(all_items)
    risk = _risk_level(score, hacks, fg["value"])
    events = _key_events(all_items, hacks)
    action = _vasily_action(score, risk)

    signal = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sentiment": _sentiment_label(score),
        "score": score,
        "fear_greed": {
            "value": fg["value"],
            "label": fg["label"],
            "trend": fg["trend"],
        },
        "key_events": events,
        "affected_assets": affected,
        "trending_coins": trending,
        "risk_level": risk,
        "vasily_action": action,
        "news_count": len(rss_news),
        "hacks_detected": len(hacks),
        "fetch_time_sec": round(time.time() - start, 2),
    }

    _save_cache(signal)
    log.info(
        "NewsAgent: done in %.2fs | score=%.3f | sentiment=%s | risk=%s",
        signal["fetch_time_sec"], score, signal["sentiment"], risk,
    )
    return signal


def format_signal_for_vasily(signal: dict) -> str:
    """Форматируем сигнал для включения в промпт Василия."""
    ts = signal.get("timestamp", "")[:16].replace("T", " ")
    score = signal.get("score", 0)
    sentiment = signal.get("sentiment", "neutral")
    risk = signal.get("risk_level", "MEDIUM")
    action = signal.get("vasily_action", "NORMAL")
    fg = signal.get("fear_greed", {})
    events = signal.get("key_events", [])
    affected = signal.get("affected_assets", [])
    trending = signal.get("trending_coins", [])
    hacks = signal.get("hacks_detected", 0)

    score_bar = "█" * int(abs(score) * 10) + "░" * (10 - int(abs(score) * 10))
    direction = "+" if score >= 0 else "-"
    emoji = {"bullish": "🟢", "slightly_bullish": "🟡", "neutral": "⚪",
              "slightly_bearish": "🟠", "bearish": "🔴"}.get(sentiment, "⚪")

    lines = [
        f"═══════════════ NEWS AGENT SIGNAL ({ts} UTC) ═══════════════",
        f"Sentiment: {emoji} {sentiment.upper()} | Score: {direction}{abs(score):.2f} [{score_bar}]",
        f"Fear & Greed: {fg.get('value', '?')} ({fg.get('label', '')}) — trend: {fg.get('trend', '')}",
        f"Risk Level: {risk}",
        f"📡 Vasily Action: {action}",
    ]

    if hacks > 0:
        lines.append(f"⚠️ HACKS DETECTED: {hacks} incident(s)!")

    if events:
        lines.append("\nKey Events:")
        for i, ev in enumerate(events, 1):
            lines.append(f"  {i}. {ev}")

    if affected:
        lines.append(f"\nAffected Assets: {', '.join(affected)}")

    if trending:
        lines.append(f"Trending (CG): {', '.join(trending)}")

    lines.append("═" * 55)
    return "\n".join(lines)


def format_signal_for_telegram(signal: dict) -> str:
    """Форматируем сигнал для ответа в Telegram (HTML-safe)."""
    ts = signal.get("timestamp", "")[:16].replace("T", " ")
    score = signal.get("score", 0)
    sentiment = signal.get("sentiment", "neutral")
    risk = signal.get("risk_level", "MEDIUM")
    action = signal.get("vasily_action", "NORMAL")
    fg = signal.get("fear_greed", {})
    events = signal.get("key_events", [])
    affected = signal.get("affected_assets", [])
    trending = signal.get("trending_coins", [])
    hacks = signal.get("hacks_detected", 0)
    age_min = round((time.time() - signal.get("cached_at", time.time())) / 60)

    emoji_map = {"bullish": "🟢", "slightly_bullish": "🟡", "neutral": "⚪",
                 "slightly_bearish": "🟠", "bearish": "🔴"}
    risk_emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴", "CRITICAL": "🆘"}

    lines = [
        f"📡 <b>News Agent Signal</b> ({ts} UTC)",
        f"Данным {age_min} мин",
        "",
        f"{emoji_map.get(sentiment, '⚪')} <b>Сентимент:</b> {sentiment.upper()} ({score:+.2f})",
        f"😨 <b>Fear & Greed:</b> {fg.get('value', '?')} — {fg.get('label', '')} ({fg.get('trend', '')})",
        f"{risk_emoji.get(risk, '⚪')} <b>Risk Level:</b> {risk}",
        f"⚡ <b>Действие:</b> {action}",
    ]

    if hacks > 0:
        lines.append(f"\n⚠️ <b>ВЗЛОМЫ ОБНАРУЖЕНЫ: {hacks}</b>")

    if events:
        lines.append("\n📰 <b>Ключевые события:</b>")
        for ev in events[:4]:
            # Escape HTML
            ev_safe = ev.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            lines.append(f"• {ev_safe}")

    if affected:
        lines.append(f"\n🎯 <b>Затронуто:</b> {', '.join(affected)}")

    if trending:
        lines.append(f"🔥 <b>Trending:</b> {', '.join(trending)}")

    return "\n".join(lines)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    signal = get_news_signal(force_refresh=True)
    print(format_signal_for_vasily(signal))
    print()
    print("Raw JSON:")
    print(json.dumps(signal, indent=2, ensure_ascii=False))
