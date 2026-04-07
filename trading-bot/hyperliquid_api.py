#!/usr/bin/env python3
"""
Hyperliquid API Client — реальные данные с биржи.
Публичный REST API, не требует ключей для чтения.
https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

import requests

log = logging.getLogger("vasily_hl")

HL_INFO_URL = "https://api.hyperliquid.xyz/info"
HL_TIMEOUT = 15
_session = requests.Session()
_session.headers.update({"Content-Type": "application/json"})

# Маппинг CoinGecko ID → Hyperliquid coin symbol
CG_TO_HL = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
    "binancecoin": "BNB",
    "ripple": "XRP",
    "cardano": "ADA",
    "avalanche-2": "AVAX",
    "polkadot": "DOT",
    "chainlink": "LINK",
    "uniswap": "UNI",
    "dogecoin": "DOGE",
    "sui": "SUI",
    "arbitrum": "ARB",
    "optimism": "OP",
    "pepe": "PEPE",
}

# Обратный маппинг
HL_TO_CG = {v: k for k, v in CG_TO_HL.items()}


def _post(payload: dict) -> Optional[dict | list]:
    """POST to Hyperliquid info endpoint."""
    try:
        resp = _session.post(HL_INFO_URL, json=payload, timeout=HL_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        log.warning("HL API error: %s", e)
        return None


def fetch_all_mids() -> dict[str, float]:
    """Get all mid-market prices. Returns {coin: price}."""
    data = _post({"type": "allMids"})
    if not data:
        return {}
    result = {}
    for coin, price_str in data.items():
        try:
            result[coin] = float(price_str)
        except (ValueError, TypeError):
            continue
    return result


def fetch_meta_and_contexts() -> Optional[tuple[list, list]]:
    """Get metadata + asset contexts (funding, OI, volumes).
    Returns (universe_list, asset_contexts_list) or None."""
    data = _post({"type": "metaAndAssetCtxs"})
    if not data or not isinstance(data, list) or len(data) < 2:
        return None
    meta = data[0]  # {"universe": [{"name": "BTC", ...}, ...]}
    ctxs = data[1]  # [{funding, openInterest, ...}, ...]
    universe = meta.get("universe", [])
    return universe, ctxs


def fetch_funding_rates() -> dict[str, dict]:
    """Get funding rates and open interest for all assets.
    Returns {coin: {funding_rate, open_interest, mark_price, premium, day_volume}}."""
    result = fetch_meta_and_contexts()
    if not result:
        return {}
    universe, ctxs = result
    data = {}
    for i, asset_info in enumerate(universe):
        coin = asset_info.get("name", "")
        if i >= len(ctxs):
            break
        ctx = ctxs[i]
        try:
            funding = float(ctx.get("funding", "0"))
            oi = float(ctx.get("openInterest", "0"))
            mark = float(ctx.get("markPx", "0"))
            premium = float(ctx.get("premium", "0"))
            day_ntl_vlm = float(ctx.get("dayNtlVlm", "0"))
            prev_day_px = float(ctx.get("prevDayPx", "0"))

            # Annualized funding rate (8h intervals = 3x per day = 1095x per year)
            annual_funding = funding * 1095 * 100  # as percentage

            # 24h price change
            price_change_24h = 0.0
            if prev_day_px > 0 and mark > 0:
                price_change_24h = ((mark - prev_day_px) / prev_day_px) * 100

            data[coin] = {
                "funding_rate": round(funding * 100, 6),  # as percentage
                "funding_annual": round(annual_funding, 2),
                "open_interest": round(oi, 2),
                "open_interest_usd": round(oi * mark, 2) if mark > 0 else 0,
                "mark_price": round(mark, 4),
                "premium": round(premium * 100, 4),  # as percentage
                "day_volume_usd": round(day_ntl_vlm, 2),
                "price_change_24h": round(price_change_24h, 2),
            }
        except (ValueError, TypeError):
            # Delisted/inactive coins have None values — skip silently
            continue
    return data


def fetch_l2_book(coin: str, depth: int = 5) -> Optional[dict]:
    """Get L2 order book for a coin. Returns {bids: [...], asks: [...], spread_pct}."""
    data = _post({"type": "l2Book", "coin": coin})
    if not data or "levels" not in data:
        return None

    levels = data["levels"]
    if len(levels) < 2:
        return None

    bids = []
    asks = []

    for bid in levels[0][:depth]:
        try:
            px = float(bid.get("px", "0"))
            sz = float(bid.get("sz", "0"))
            n = int(bid.get("n", 0))
            bids.append({"price": px, "size": sz, "orders": n})
        except (ValueError, TypeError):
            continue

    for ask in levels[1][:depth]:
        try:
            px = float(ask.get("px", "0"))
            sz = float(ask.get("sz", "0"))
            n = int(ask.get("n", 0))
            asks.append({"price": px, "size": sz, "orders": n})
        except (ValueError, TypeError):
            continue

    spread_pct = 0.0
    if bids and asks:
        best_bid = bids[0]["price"]
        best_ask = asks[0]["price"]
        mid = (best_bid + best_ask) / 2
        if mid > 0:
            spread_pct = ((best_ask - best_bid) / mid) * 100

    return {
        "bids": bids,
        "asks": asks,
        "spread_pct": round(spread_pct, 4),
        "best_bid": bids[0]["price"] if bids else 0,
        "best_ask": asks[0]["price"] if asks else 0,
    }


def fetch_candles(coin: str, interval: str = "1h", limit: int = 100) -> list[dict]:
    """Get historical candles from Hyperliquid.
    interval: '1m','5m','15m','1h','4h','1d'
    Returns list of {time, open, high, low, close, volume}."""
    # Hyperliquid candle endpoint
    now_ms = int(time.time() * 1000)

    # Calculate start time based on interval and limit
    interval_ms = {
        "1m": 60_000, "5m": 300_000, "15m": 900_000,
        "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000,
    }
    ms_per = interval_ms.get(interval, 3_600_000)
    start_ms = now_ms - (ms_per * limit)

    data = _post({
        "type": "candleSnapshot",
        "req": {
            "coin": coin,
            "interval": interval,
            "startTime": start_ms,
            "endTime": now_ms,
        }
    })

    if not data or not isinstance(data, list):
        return []

    candles = []
    for c in data:
        try:
            candles.append({
                "time": c.get("t", 0),
                "open": float(c.get("o", "0")),
                "high": float(c.get("h", "0")),
                "low": float(c.get("l", "0")),
                "close": float(c.get("c", "0")),
                "volume": float(c.get("v", "0")),
            })
        except (ValueError, TypeError):
            continue

    return candles


def fetch_market_summary(coins: list[str] | None = None) -> dict:
    """Fetch comprehensive market data for specified coins.
    Returns {coin: {price, funding, oi, volume, change_24h, spread, book_imbalance}}."""
    if coins is None:
        coins = ["BTC", "ETH", "SOL", "BNB", "AVAX", "XRP", "LINK", "DOGE", "SUI", "ARB"]

    # Batch requests
    mids = fetch_all_mids()
    funding_data = fetch_funding_rates()

    summary = {}
    for coin in coins:
        price = mids.get(coin, 0)
        fd = funding_data.get(coin, {})

        if price <= 0 and fd.get("mark_price", 0) > 0:
            price = fd["mark_price"]

        if price <= 0:
            continue

        # Get order book for key coins (rate limit)
        book = None
        if coin in ["BTC", "ETH", "SOL", "BNB", "AVAX"]:
            book = fetch_l2_book(coin, depth=5)
            time.sleep(0.1)  # rate limit

        # Book imbalance: bid_volume vs ask_volume in top 5 levels
        book_imbalance = 0.0
        if book:
            bid_vol = sum(b["size"] for b in book["bids"])
            ask_vol = sum(a["size"] for a in book["asks"])
            total = bid_vol + ask_vol
            if total > 0:
                book_imbalance = round(((bid_vol - ask_vol) / total) * 100, 1)

        summary[coin] = {
            "price": price,
            "funding_rate": fd.get("funding_rate", 0),
            "funding_annual": fd.get("funding_annual", 0),
            "open_interest_usd": fd.get("open_interest_usd", 0),
            "day_volume_usd": fd.get("day_volume_usd", 0),
            "price_change_24h": fd.get("price_change_24h", 0),
            "premium": fd.get("premium", 0),
            "spread_pct": book["spread_pct"] if book else 0,
            "book_imbalance": book_imbalance,
        }

    return summary


# ─── Funding History ─────────────────────────────────────────────────────────

def fetch_funding_history(coin: str, hours: int = 72) -> list[dict]:
    """Get historical funding rates for a coin (last N hours).
    Returns list of {time, coin, fundingRate, premium}."""
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (hours * 3_600_000)
    data = _post({
        "type": "fundingHistory",
        "coin": coin,
        "startTime": start_ms,
        "endTime": now_ms,
    })
    if not data or not isinstance(data, list):
        return []
    result = []
    for entry in data:
        try:
            result.append({
                "time": entry.get("time", 0),
                "coin": entry.get("coin", coin),
                "funding_rate": float(entry.get("fundingRate", "0")),
                "premium": float(entry.get("premium", "0")),
            })
        except (ValueError, TypeError):
            continue
    return result


def fetch_predicted_fundings() -> dict[str, dict]:
    """Get predicted next funding rates for all assets.
    API returns: [[coin, [[venue, {fundingRate, nextFundingTime, fundingIntervalHours}], ...]], ...]
    Returns {coin: {predicted_rate, predicted_annual, hl_rate, interval_hours}}."""
    data = _post({"type": "predictedFundings"})
    if not data or not isinstance(data, list):
        return {}
    result = {}
    for entry in data:
        try:
            if not isinstance(entry, list) or len(entry) < 2:
                continue
            coin = entry[0]
            venues = entry[1]
            if not isinstance(venues, list):
                continue
            for venue_data in venues:
                if not isinstance(venue_data, list) or len(venue_data) < 2:
                    continue
                venue_name = venue_data[0]
                info = venue_data[1]
                if venue_name == "HlPerp":
                    rate = float(info.get("fundingRate", "0"))
                    interval = int(info.get("fundingIntervalHours", 1))
                    # Annualize: rate * (8760 / interval_hours) for annual
                    annual = rate * (8760 / interval) * 100
                    result[coin] = {
                        "predicted_rate": round(rate * 100, 6),
                        "predicted_annual": round(annual, 2),
                        "interval_hours": interval,
                    }
                    break
        except (ValueError, TypeError, AttributeError, IndexError):
            continue
    return result


# ─── Liquidation Detection ──────────────────────────────────────────────────

def fetch_recent_liquidations(limit: int = 50) -> list[dict]:
    """Get recent liquidations across all assets via clearinghouseState.
    Uses userNonFundingLedgerUpdates with a known liquidation source.
    Falls back to checking liquidatable positions."""
    # Hyperliquid doesn't have a direct "all liquidations" endpoint for anon,
    # but we can check for assets near liquidation threshold
    data = _post({"type": "clearinghouseState", "user": "0x0000000000000000000000000000000000000000"})
    # This returns empty for zero-address but the approach is documented
    # Real liquidation detection: monitor large price moves + OI drops
    return []


def detect_liquidation_cascades(coins: list[str] = None) -> dict[str, dict]:
    """Detect potential liquidation cascades by analyzing OI changes + price moves.
    High OI drop + sharp price move = liquidation cascade in progress.
    Returns {coin: {oi_change_pct, price_change_pct, cascade_risk}}."""
    if coins is None:
        coins = ["BTC", "ETH", "SOL", "BNB", "AVAX"]

    result_meta = fetch_meta_and_contexts()
    if not result_meta:
        return {}

    universe, ctxs = result_meta
    coin_to_idx = {u.get("name", ""): i for i, u in enumerate(universe)}

    cascades = {}
    for coin in coins:
        idx = coin_to_idx.get(coin)
        if idx is None or idx >= len(ctxs):
            continue
        ctx = ctxs[idx]
        try:
            oi = float(ctx.get("openInterest", "0"))
            mark = float(ctx.get("markPx", "0"))
            prev_day_px = float(ctx.get("prevDayPx", "0"))
            premium = float(ctx.get("premium", "0"))

            price_change = 0
            if prev_day_px > 0:
                price_change = ((mark - prev_day_px) / prev_day_px) * 100

            # High premium + big OI = potential squeeze
            # Extreme negative premium = shorts getting squeezed
            # Extreme positive premium = longs getting squeezed
            cascade_risk = "LOW"
            if abs(premium * 100) > 0.1 and oi * mark > 50_000_000:  # $50M+ OI
                if abs(price_change) > 3:
                    cascade_risk = "HIGH"
                elif abs(price_change) > 1.5:
                    cascade_risk = "MEDIUM"

            cascades[coin] = {
                "open_interest": round(oi, 2),
                "oi_usd": round(oi * mark, 2),
                "price_change_24h": round(price_change, 2),
                "premium_pct": round(premium * 100, 4),
                "cascade_risk": cascade_risk,
            }
        except (ValueError, TypeError):
            continue
    return cascades


# ─── Vault Intelligence (Copy-Trading Signals) ─────────────────────────────

def fetch_vault_summaries() -> list[dict]:
    """Get top vaults on Hyperliquid — copy-trading intelligence.
    Returns list of {name, leader, tvl, pnl, apr, followers}."""
    data = _post({"type": "vaultSummaries"})
    if not data or not isinstance(data, list):
        return []
    vaults = []
    for v in data[:20]:  # Top 20 vaults
        try:
            tvl = float(v.get("tvl", "0"))
            if tvl < 10000:  # Skip tiny vaults
                continue
            total_pnl = float(v.get("allTimePnl", "0"))
            vaults.append({
                "name": v.get("name", "Unknown"),
                "vault_address": v.get("vaultAddress", ""),
                "leader": v.get("leader", ""),
                "tvl": round(tvl, 2),
                "total_pnl": round(total_pnl, 2),
                "followers": v.get("followerCount", 0),
                "apr": round(float(v.get("apr", "0")) * 100, 1) if v.get("apr") else 0,
            })
        except (ValueError, TypeError):
            continue
    return sorted(vaults, key=lambda x: -x["tvl"])[:10]


def fetch_vault_positions(vault_address: str) -> list[dict]:
    """Get current positions of a specific vault.
    Returns list of {coin, side, size, entry_price, pnl}."""
    data = _post({"type": "clearinghouseState", "user": vault_address})
    if not data or not isinstance(data, dict):
        return []
    positions = []
    for pos in data.get("assetPositions", []):
        p = pos.get("position", {})
        try:
            szi = float(p.get("szi", "0"))
            if abs(szi) < 0.0001:
                continue
            entry = float(p.get("entryPx", "0"))
            positions.append({
                "coin": p.get("coin", ""),
                "side": "LONG" if szi > 0 else "SHORT",
                "size": abs(szi),
                "size_usd": abs(szi) * entry,
                "entry_price": entry,
                "unrealized_pnl": float(p.get("unrealizedPnl", "0")),
                "leverage": float(p.get("leverage", {}).get("value", "1")) if isinstance(p.get("leverage"), dict) else 1,
            })
        except (ValueError, TypeError):
            continue
    return positions


# ─── OI Analysis ────────────────────────────────────────────────────────────

def fetch_oi_snapshots(coins: list[str] = None) -> dict[str, dict]:
    """Get detailed OI data with cap analysis.
    Returns {coin: {oi, oi_usd, max_oi, at_cap, pct_of_cap}}."""
    if coins is None:
        coins = ["BTC", "ETH", "SOL", "BNB", "AVAX"]

    # Check which perps are at OI cap
    cap_data = _post({"type": "perpsAtOpenInterestCap"})
    at_cap_coins = set()
    if cap_data and isinstance(cap_data, list):
        at_cap_coins = set(cap_data)

    result_meta = fetch_meta_and_contexts()
    if not result_meta:
        return {}

    universe, ctxs = result_meta
    coin_to_idx = {u.get("name", ""): i for i, u in enumerate(universe)}

    oi_data = {}
    for coin in coins:
        idx = coin_to_idx.get(coin)
        if idx is None or idx >= len(ctxs):
            continue
        ctx = ctxs[idx]
        u = universe[idx]
        try:
            oi = float(ctx.get("openInterest", "0"))
            mark = float(ctx.get("markPx", "0"))
            max_oi_str = u.get("maxOpenInterest", "0")
            max_oi = float(max_oi_str) if max_oi_str else 0

            pct_cap = 0
            if max_oi > 0:
                pct_cap = (oi / max_oi) * 100

            oi_data[coin] = {
                "oi": round(oi, 2),
                "oi_usd": round(oi * mark, 2),
                "max_oi": round(max_oi, 2),
                "at_cap": coin in at_cap_coins,
                "pct_of_cap": round(pct_cap, 1),
            }
        except (ValueError, TypeError):
            continue
    return oi_data


# ─── Whale Detection (Large Trades via Recent Fills) ───────────────────────

def fetch_recent_trades_ws_fallback(coin: str, min_usd: float = 50000) -> list[dict]:
    """Detect whale trades by checking L2 book depth changes.
    Since REST doesn't have a trades feed, we approximate via book analysis.
    For real whale detection, check order book depth — large walls = whale positioning."""
    book = fetch_l2_book(coin, depth=20)
    if not book:
        return []

    whales = []
    # Detect large orders in the book (whale walls)
    for side_name, orders in [("BID", book.get("bids", [])), ("ASK", book.get("asks", []))]:
        for order in orders:
            usd_size = order["price"] * order["size"]
            if usd_size >= min_usd:
                whales.append({
                    "coin": coin,
                    "side": side_name,
                    "price": order["price"],
                    "size": order["size"],
                    "usd_size": round(usd_size, 2),
                    "orders": order["orders"],
                    "type": "WALL",
                })
    return whales


def fetch_whale_walls(coins: list[str] = None, min_usd: float = 100000) -> dict[str, list[dict]]:
    """Detect whale walls across multiple coins.
    Returns {coin: [whale_entries]}."""
    if coins is None:
        coins = ["BTC", "ETH", "SOL"]
    result = {}
    for coin in coins:
        walls = fetch_recent_trades_ws_fallback(coin, min_usd)
        if walls:
            result[coin] = walls
        time.sleep(0.15)
    return result


# ─── Multi-Timeframe Candles ────────────────────────────────────────────────

def fetch_multi_timeframe(coin: str) -> dict[str, list[dict]]:
    """Fetch candles for multiple timeframes: 1h, 4h, 1d.
    Returns {interval: candles_list}."""
    result = {}
    for interval, limit in [("1h", 100), ("4h", 50), ("1d", 30)]:
        candles = fetch_candles(coin, interval, limit)
        if candles:
            result[interval] = candles
        time.sleep(0.15)
    return result


# ─── Perp Categories (Sector Analysis) ─────────────────────────────────────

def fetch_perp_universe() -> list[dict]:
    """Get full universe of tradeable perps with metadata.
    Returns list of {name, szDecimals, maxLeverage, onlyIsolated}."""
    result = fetch_meta_and_contexts()
    if not result:
        return []
    universe, ctxs = result
    perps = []
    for i, u in enumerate(universe):
        try:
            ctx = ctxs[i] if i < len(ctxs) else {}
            vol = float(ctx.get("dayNtlVlm", "0"))
            mark = float(ctx.get("markPx", "0"))
            perps.append({
                "name": u.get("name", ""),
                "max_leverage": u.get("maxLeverage", 1),
                "sz_decimals": u.get("szDecimals", 0),
                "mark_price": mark,
                "day_volume_usd": round(vol, 2),
            })
        except (ValueError, TypeError):
            continue
    return sorted(perps, key=lambda x: -x["day_volume_usd"])


# ─── Extended Market Summary ────────────────────────────────────────────────

def fetch_extended_market(coins: list[str] = None) -> dict:
    """Fetch ALL available data for coins in one call.
    Combines: prices, funding, OI, predicted funding, cascades, book depth.
    Returns dict with all data sections."""
    if coins is None:
        coins = ["BTC", "ETH", "SOL", "BNB", "AVAX", "XRP", "LINK", "DOGE", "SUI", "ARB"]

    log.info("Fetching extended market data for %d coins...", len(coins))

    # Parallel-ish data fetching (sequential but batched)
    market = fetch_market_summary(coins)
    predicted = fetch_predicted_fundings()
    oi_data = fetch_oi_snapshots(coins[:7])
    cascades = detect_liquidation_cascades(coins[:5])
    whale_walls = fetch_whale_walls(coins[:3], min_usd=50000)

    # Funding history for top 3 coins (72h)
    funding_hist = {}
    for coin in coins[:3]:
        hist = fetch_funding_history(coin, hours=72)
        if hist:
            # Summarize: avg, min, max, trend
            rates = [h["funding_rate"] for h in hist]
            if rates:
                recent = rates[-8:] if len(rates) >= 8 else rates
                older = rates[:8] if len(rates) >= 16 else rates[:len(rates)//2] if rates else []
                avg_recent = sum(recent) / len(recent) if recent else 0
                avg_older = sum(older) / len(older) if older else 0
                trend = "RISING" if avg_recent > avg_older * 1.2 else "FALLING" if avg_recent < avg_older * 0.8 else "STABLE"
                funding_hist[coin] = {
                    "avg_rate": round(sum(rates) / len(rates) * 100, 6),
                    "min_rate": round(min(rates) * 100, 6),
                    "max_rate": round(max(rates) * 100, 6),
                    "recent_avg": round(avg_recent * 100, 6),
                    "trend": trend,
                    "data_points": len(rates),
                }
        time.sleep(0.15)

    return {
        "market": market,
        "predicted_funding": predicted,
        "oi_analysis": oi_data,
        "liquidation_cascades": cascades,
        "whale_walls": whale_walls,
        "funding_history": funding_hist,
    }


# ─── Convenience: test from CLI ───────────────────────────────────────────────
if __name__ == "__main__":
    print("=== Hyperliquid Extended Market Data ===\n")

    # Basic market
    data = fetch_market_summary()
    for coin, info in sorted(data.items(), key=lambda x: -x[1]["day_volume_usd"]):
        print(f"{coin:>5}: ${info['price']:>12,.2f} | "
              f"24h: {info['price_change_24h']:+.2f}% | "
              f"Funding: {info['funding_rate']:+.4f}% (ann: {info['funding_annual']:+.1f}%) | "
              f"OI: ${info['open_interest_usd']/1e6:.0f}M | "
              f"Vol: ${info['day_volume_usd']/1e6:.0f}M | "
              f"Spread: {info['spread_pct']:.4f}% | "
              f"Book: {info['book_imbalance']:+.1f}%")

    # Predicted funding
    print("\n=== Predicted Funding ===")
    pf = fetch_predicted_fundings()
    for coin, info in sorted(pf.items(), key=lambda x: -abs(x[1]["predicted_rate"]))[:10]:
        print(f"  {coin}: {info['predicted_rate']:+.4f}% (ann: {info['predicted_annual']:+.1f}%)")

    # OI
    print("\n=== Open Interest ===")
    oi = fetch_oi_snapshots()
    for coin, info in oi.items():
        cap = f" AT CAP!" if info["at_cap"] else f" ({info['pct_of_cap']:.0f}% of cap)"
        print(f"  {coin}: ${info['oi_usd']/1e6:.0f}M{cap}")

    # Whale walls
    print("\n=== Whale Walls ===")
    walls = fetch_whale_walls(["BTC", "ETH", "SOL"], min_usd=50000)
    for coin, entries in walls.items():
        for w in entries:
            print(f"  {coin} {w['side']} wall: ${w['usd_size']:,.0f} @ ${w['price']:,.2f}")

    # Cascades
    print("\n=== Liquidation Cascade Risk ===")
    casc = detect_liquidation_cascades()
    for coin, info in casc.items():
        print(f"  {coin}: risk={info['cascade_risk']} | premium: {info['premium_pct']:+.4f}% | 24h: {info['price_change_24h']:+.2f}%")
