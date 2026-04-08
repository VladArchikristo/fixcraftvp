#!/usr/bin/env python3
"""
Hyperliquid Local Strategies — Василий Trading Intelligence.
Все стратегии работают только на данных Hyperliquid (без арбитража между биржами).

Стратегии:
1. Funding Rate Extremes — mean reversion при экстремальном фандинге
2. OI Divergence — расхождение OI и цены (ликвидации, squeeze)
3. Whale Wall Analysis — крупные ордера в стакане
4. Multi-Timeframe Confluence — совпадение сигналов на 1h/4h/1d
5. Vault Copy Signals — что делают топ-фонды на Hyperliquid
6. Liquidation Cascade — каскадные ликвидации = быстрые движения
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("vasily_strat")


# ─── 1. Funding Rate Extremes ──────────────────────────────────────────────

def analyze_funding_extremes(
    funding_data: dict,
    predicted_funding: dict = None,
    funding_history: dict = None,
    threshold_high: float = 0.01,   # 0.01% per 8h = extreme
    threshold_low: float = -0.01,
) -> list[dict]:
    """Detect funding rate extremes — potential mean reversion opportunities.

    Logic:
    - Extreme positive funding → crowd is LONG → potential LONG squeeze → SHORT signal
    - Extreme negative funding → crowd is SHORT → potential SHORT squeeze → LONG signal
    - Rising funding trend amplifies signal
    - Predicted funding confirms direction

    Returns list of {coin, signal, funding_rate, strength, reason}.
    """
    signals = []

    for coin, data in funding_data.items():
        fr = data.get("funding_rate", 0)
        if abs(fr) < abs(threshold_high) * 0.5:
            continue  # Not interesting

        strength = 0
        reasons = []

        # Current funding extreme
        if fr > threshold_high:
            direction = "SHORT"  # fade the crowd
            strength += min(30, int(fr / threshold_high * 15))
            reasons.append(f"Funding {fr:+.4f}% — longs overpaying")
        elif fr < threshold_low:
            direction = "LONG"  # fade the crowd
            strength += min(30, int(abs(fr) / abs(threshold_low) * 15))
            reasons.append(f"Funding {fr:+.4f}% — shorts overpaying")
        else:
            continue

        # Predicted funding amplifies
        pred = (predicted_funding or {}).get(coin, {})
        pred_rate = pred.get("predicted_rate", 0)
        if pred_rate != 0:
            same_direction = (pred_rate > 0 and fr > 0) or (pred_rate < 0 and fr < 0)
            if same_direction and abs(pred_rate) > abs(fr):
                strength += 10
                reasons.append(f"Predicted funding HIGHER: {pred_rate:+.4f}%")
            elif not same_direction:
                strength -= 10
                reasons.append(f"Predicted funding FLIPPING: {pred_rate:+.4f}%")

        # Funding history trend
        hist = (funding_history or {}).get(coin, {})
        if hist:
            trend = hist.get("trend", "STABLE")
            if trend == "RISING" and fr > 0:
                strength += 10
                reasons.append("Funding trend RISING — crowd getting more leveraged long")
            elif trend == "FALLING" and fr < 0:
                strength += 10
                reasons.append("Funding trend FALLING — crowd getting more leveraged short")
            elif trend == "STABLE":
                strength += 5
                reasons.append("Funding sustained — not a spike")

        if strength >= 15:
            signals.append({
                "coin": coin,
                "signal": direction,
                "strategy": "FUNDING_EXTREME",
                "funding_rate": fr,
                "strength": min(50, strength),
                "reason": "; ".join(reasons),
            })

    return sorted(signals, key=lambda x: -x["strength"])


# ─── 2. OI Divergence ──────────────────────────────────────────────────────

def analyze_oi_divergence(
    market_data: dict,
    oi_data: dict = None,
    cascade_data: dict = None,
) -> list[dict]:
    """Detect OI divergences with price — key liquidity signals.

    Logic:
    - Price UP + OI UP = new longs entering (bullish continuation)
    - Price UP + OI DOWN = shorts closing (weaker rally, potential reversal)
    - Price DOWN + OI UP = new shorts entering (bearish continuation)
    - Price DOWN + OI DOWN = longs closing (weaker sell-off, potential bottom)
    - At OI cap = no new positions can open, existing positions dominate

    Returns list of {coin, signal, strength, reason}.
    """
    signals = []

    for coin, data in market_data.items():
        price_change = data.get("price_change_24h", 0)
        oi_info = (oi_data or {}).get(coin, {})
        casc = (cascade_data or {}).get(coin, {})

        if not oi_info:
            continue

        reasons = []
        strength = 0
        direction = None

        # OI cap analysis
        if oi_info.get("at_cap"):
            reasons.append(f"OI AT CAP — no new positions possible!")
            strength += 15

        pct_cap = oi_info.get("pct_of_cap", 0)
        if pct_cap > 90:
            reasons.append(f"OI at {pct_cap:.0f}% of cap — nearly maxed")
            strength += 10

        # Cascade risk
        cascade_risk = casc.get("cascade_risk", "LOW")
        premium = casc.get("premium_pct", 0)
        if cascade_risk == "HIGH":
            strength += 20
            if premium > 0:
                direction = "SHORT"
                reasons.append(f"HIGH cascade risk — premium {premium:+.4f}%, longs at risk")
            else:
                direction = "LONG"
                reasons.append(f"HIGH cascade risk — premium {premium:+.4f}%, shorts at risk")
        elif cascade_risk == "MEDIUM":
            strength += 10
            reasons.append(f"MEDIUM cascade risk — watch for liquidation spike")

        # Price vs OI divergence (simplified — we'd need historical OI for proper calc)
        oi_usd = oi_info.get("oi_usd", 0)
        vol_usd = data.get("day_volume_usd", 0)
        if vol_usd > 0 and oi_usd > 0:
            # High OI/Volume ratio = crowded trade
            oi_vol_ratio = oi_usd / vol_usd
            if oi_vol_ratio > 5:
                strength += 10
                reasons.append(f"OI/Volume ratio {oi_vol_ratio:.1f}x — crowded trade")
            elif oi_vol_ratio < 1:
                reasons.append(f"OI/Volume ratio {oi_vol_ratio:.1f}x — active turnover")

        if strength >= 15 and reasons:
            signals.append({
                "coin": coin,
                "signal": direction or ("SHORT" if price_change > 0 else "LONG"),
                "strategy": "OI_DIVERGENCE",
                "strength": min(50, strength),
                "reason": "; ".join(reasons),
            })

    return sorted(signals, key=lambda x: -x["strength"])


# ─── 3. Whale Wall Analysis ────────────────────────────────────────────────

def analyze_whale_walls(whale_walls: dict, market_data: dict = None) -> list[dict]:
    """Analyze whale order walls for directional signals.

    Logic:
    - Large BID wall near current price = support, bullish
    - Large ASK wall near current price = resistance, bearish
    - Walls far from price = less relevant
    - Multiple walls on same side = strong signal

    Returns list of {coin, signal, strength, reason}.
    """
    signals = []

    for coin, walls in whale_walls.items():
        if not walls:
            continue

        price = (market_data or {}).get(coin, {}).get("price", 0)
        if price <= 0:
            continue

        bid_usd = sum(w["usd_size"] for w in walls if w["side"] == "BID")
        ask_usd = sum(w["usd_size"] for w in walls if w["side"] == "ASK")
        total = bid_usd + ask_usd

        if total < 100_000:  # Minimum $100k in walls
            continue

        strength = 0
        reasons = []

        # Imbalance analysis
        if total > 0:
            bid_pct = (bid_usd / total) * 100
            ask_pct = (ask_usd / total) * 100

            if bid_pct > 70:
                direction = "LONG"
                strength += 20
                reasons.append(f"BID walls {bid_pct:.0f}% of total ${total/1000:.0f}K")
            elif ask_pct > 70:
                direction = "SHORT"
                strength += 20
                reasons.append(f"ASK walls {ask_pct:.0f}% of total ${total/1000:.0f}K")
            else:
                direction = "NEUTRAL"
                reasons.append(f"Balanced walls: BID {bid_pct:.0f}% / ASK {ask_pct:.0f}%")

            # Proximity to current price amplifies
            for w in walls:
                dist_pct = abs(w["price"] - price) / price * 100
                if dist_pct < 0.5:
                    strength += 10
                    reasons.append(f"Wall at ${w['price']:,.2f} VERY CLOSE ({dist_pct:.2f}%)")
                elif dist_pct < 1.0:
                    strength += 5

        if strength >= 15 and direction != "NEUTRAL":
            signals.append({
                "coin": coin,
                "signal": direction,
                "strategy": "WHALE_WALLS",
                "strength": min(40, strength),
                "reason": "; ".join(reasons),
            })

    return sorted(signals, key=lambda x: -x["strength"])


# ─── 4. Multi-Timeframe Confluence ─────────────────────────────────────────

def analyze_multi_timeframe(
    ta_1h: dict,
    ta_4h: dict = None,
    ta_1d: dict = None,
) -> dict:
    """Check if signals align across timeframes.

    Logic:
    - All timeframes agree = STRONG signal (multiply strength)
    - 2 of 3 agree = MODERATE signal
    - Mixed = WEAK / NO signal

    Returns {confluence_score, direction, aligned_tfs, details}.
    """
    scores = {}

    for label, ta in [("1h", ta_1h), ("4h", ta_4h), ("1d", ta_1d)]:
        if not ta:
            continue
        score = ta.get("score", 0)
        rec = ta.get("recommendation", "NEUTRAL")
        scores[label] = {
            "score": score,
            "recommendation": rec,
            "direction": "LONG" if score > 0 else "SHORT" if score < 0 else "NEUTRAL",
        }

    if not scores:
        return {"confluence_score": 0, "direction": "NEUTRAL", "aligned_tfs": [], "details": "No TA data"}

    directions = [v["direction"] for v in scores.values()]
    long_count = directions.count("LONG")
    short_count = directions.count("SHORT")
    total = len(directions)

    aligned_tfs = []
    if long_count == total:
        direction = "LONG"
        confluence = 100
        aligned_tfs = list(scores.keys())
    elif short_count == total:
        direction = "SHORT"
        confluence = 100
        aligned_tfs = list(scores.keys())
    elif long_count > short_count and long_count >= 2:
        direction = "LONG"
        confluence = 60
        aligned_tfs = [k for k, v in scores.items() if v["direction"] == "LONG"]
    elif short_count > long_count and short_count >= 2:
        direction = "SHORT"
        confluence = 60
        aligned_tfs = [k for k, v in scores.items() if v["direction"] == "SHORT"]
    else:
        direction = "NEUTRAL"
        confluence = 20

    # Weight by timeframe (1d > 4h > 1h)
    weights = {"1d": 3, "4h": 2, "1h": 1}
    weighted_score = sum(
        scores[tf]["score"] * weights.get(tf, 1) for tf in scores
    ) / sum(weights.get(tf, 1) for tf in scores)

    details = " | ".join(f"{tf}: {v['score']:+d} ({v['recommendation']})" for tf, v in scores.items())

    return {
        "confluence_score": confluence,
        "weighted_score": round(weighted_score, 1),
        "direction": direction,
        "aligned_tfs": aligned_tfs,
        "details": details,
    }


# ─── 5. Vault Copy Signals ─────────────────────────────────────────────────

def analyze_vault_signals(vaults: list[dict], vault_positions: dict = None) -> list[dict]:
    """Analyze what top vaults are doing — copy-trading intelligence.

    Logic:
    - If multiple top vaults are LONG same coin → bullish signal
    - If top vaults are exiting → bearish signal
    - Vault APR/TVL weighted

    vault_positions: {vault_address: [positions]}
    Returns list of {coin, signal, strength, reason}.
    """
    if not vault_positions:
        return []

    coin_signals = {}  # {coin: {"long": weight, "short": weight, "reasons": []}}

    for vault in vaults:
        addr = vault.get("vault_address", "")
        positions = vault_positions.get(addr, [])
        tvl = vault.get("tvl", 0)
        name = vault.get("name", "Unknown")
        apr = vault.get("apr", 0)

        # Weight by TVL (larger vaults = more signal)
        weight = min(20, max(1, tvl / 100_000))
        if apr > 50:
            weight *= 1.5  # High-performing vault

        for pos in positions:
            coin = pos["coin"]
            side = pos["side"]
            size_usd = pos.get("size_usd", 0)

            if coin not in coin_signals:
                coin_signals[coin] = {"long": 0, "short": 0, "reasons": []}

            if side == "LONG":
                coin_signals[coin]["long"] += weight
                coin_signals[coin]["reasons"].append(f"{name} LONG ${size_usd:,.0f}")
            else:
                coin_signals[coin]["short"] += weight
                coin_signals[coin]["reasons"].append(f"{name} SHORT ${size_usd:,.0f}")

    signals = []
    for coin, data in coin_signals.items():
        total = data["long"] + data["short"]
        if total < 10:
            continue

        if data["long"] > data["short"] * 1.5:
            direction = "LONG"
            strength = min(40, int(data["long"]))
        elif data["short"] > data["long"] * 1.5:
            direction = "SHORT"
            strength = min(40, int(data["short"]))
        else:
            continue

        signals.append({
            "coin": coin,
            "signal": direction,
            "strategy": "VAULT_COPY",
            "strength": strength,
            "reason": "; ".join(data["reasons"][:3]),
        })

    return sorted(signals, key=lambda x: -x["strength"])


# ─── Master Strategy Combiner ──────────────────────────────────────────────

def combine_strategies(
    funding_signals: list[dict],
    oi_signals: list[dict],
    whale_signals: list[dict],
    vault_signals: list[dict],
    confluence_data: dict[str, dict] = None,  # {coin: confluence_result}
    ta_data: dict[str, dict] = None,  # {coin: ta_analysis}
) -> list[dict]:
    """Combine all strategy signals into final recommendations.

    Each signal has a strength (0-50). We combine:
    - Strategy signals (funding, OI, whale, vault)
    - TA confluence (multi-timeframe)
    - TA score from technical analysis
    - ADX anti-trend filter: penalizes signals that go against a strong trend

    Returns sorted list of {coin, direction, total_score, strategies, recommendation}.
    """
    # Build ADX trend filter from TA data
    adx_filter = {}  # {coin: {"adx": float, "trend_dir": "LONG"|"SHORT"|None}}
    if ta_data:
        for coin, ta in ta_data.items():
            adx_info = ta.get("adx")
            if adx_info and adx_info.get("adx", 0) > 25:
                if adx_info["plus_di"] > adx_info["minus_di"]:
                    adx_filter[coin] = {"adx": adx_info["adx"], "trend_dir": "LONG"}
                else:
                    adx_filter[coin] = {"adx": adx_info["adx"], "trend_dir": "SHORT"}

    # Aggregate by coin
    coin_scores = {}

    # Collect all signals
    all_signals = (
        [(s, "funding") for s in funding_signals] +
        [(s, "oi") for s in oi_signals] +
        [(s, "whale") for s in whale_signals] +
        [(s, "vault") for s in vault_signals]
    )

    for signal, source in all_signals:
        coin = signal["coin"]
        if coin not in coin_scores:
            coin_scores[coin] = {"long": 0, "short": 0, "strategies": [], "reasons": []}

        direction = signal["signal"]
        strength = signal["strength"]

        if direction == "LONG":
            coin_scores[coin]["long"] += strength
        elif direction == "SHORT":
            coin_scores[coin]["short"] += strength

        coin_scores[coin]["strategies"].append(signal["strategy"])
        coin_scores[coin]["reasons"].append(f"[{signal['strategy']}] {signal['reason']}")

    # Add multi-timeframe confluence
    if confluence_data:
        for coin, conf in confluence_data.items():
            if coin not in coin_scores:
                coin_scores[coin] = {"long": 0, "short": 0, "strategies": [], "reasons": []}

            weighted = conf.get("weighted_score", 0)
            confluence = conf.get("confluence_score", 0)
            if confluence >= 60:
                bonus = int(abs(weighted) * 0.3)
                if weighted > 0:
                    coin_scores[coin]["long"] += bonus
                elif weighted < 0:
                    coin_scores[coin]["short"] += bonus
                coin_scores[coin]["strategies"].append("MTF_CONFLUENCE")
                coin_scores[coin]["reasons"].append(
                    f"[MTF] {conf['details']} (confluence: {confluence}%)"
                )

    # Add TA scores
    if ta_data:
        for coin, ta in ta_data.items():
            if coin not in coin_scores:
                coin_scores[coin] = {"long": 0, "short": 0, "strategies": [], "reasons": []}

            score = ta.get("score", 0)
            bonus = int(abs(score) * 0.3)
            if score > 15:
                coin_scores[coin]["long"] += bonus
            elif score < -15:
                coin_scores[coin]["short"] += bonus

    # Apply ADX anti-trend filter: penalize signals going against strong trend
    for coin, data in coin_scores.items():
        if coin in adx_filter:
            trend_dir = adx_filter[coin]["trend_dir"]
            adx_val = adx_filter[coin]["adx"]
            penalty = int(adx_val * 0.5)  # Stronger trend = bigger penalty

            if trend_dir == "LONG" and data["short"] > data["long"]:
                # Trying to SHORT in strong uptrend — penalize
                data["short"] = max(0, data["short"] - penalty)
                data["reasons"].append(f"[ADX_FILTER] Anti-trend penalty -{penalty} on SHORT (ADX={adx_val}, trend=UP)")
                data["strategies"].append("ADX_FILTER")
            elif trend_dir == "SHORT" and data["long"] > data["short"]:
                # Trying to LONG in strong downtrend — penalize
                data["long"] = max(0, data["long"] - penalty)
                data["reasons"].append(f"[ADX_FILTER] Anti-trend penalty -{penalty} on LONG (ADX={adx_val}, trend=DOWN)")
                data["strategies"].append("ADX_FILTER")

    # Build final recommendations
    results = []
    for coin, data in coin_scores.items():
        long_score = data["long"]
        short_score = data["short"]
        net = long_score - short_score

        if abs(net) < 15:
            rec = "NEUTRAL"
            direction = "NEUTRAL"
        elif net > 0:
            direction = "LONG"
            rec = "STRONG_BUY" if net > 60 else "BUY" if net > 30 else "LEAN_LONG"
        else:
            direction = "SHORT"
            rec = "STRONG_SELL" if net < -60 else "SELL" if net < -30 else "LEAN_SHORT"

        unique_strategies = list(set(data["strategies"]))

        results.append({
            "coin": coin,
            "direction": direction,
            "long_score": long_score,
            "short_score": short_score,
            "net_score": net,
            "strategies": unique_strategies,
            "strategy_count": len(unique_strategies),
            "recommendation": rec,
            "reasons": data["reasons"],
        })

    return sorted(results, key=lambda x: -abs(x["net_score"]))


def format_strategy_report(results: list[dict]) -> str:
    """Format strategy results into text for Claude prompt."""
    if not results:
        return "No strategy signals detected."

    lines = ["═══════════════ STRATEGY INTELLIGENCE ═══════════════"]

    for r in results:
        coin = r["coin"]
        direction = r["direction"]
        net = r["net_score"]
        rec = r["recommendation"]
        strats = ", ".join(r["strategies"])

        emoji = "🟢" if direction == "LONG" else "🔴" if direction == "SHORT" else "⚪"
        lines.append(f"\n{emoji} {coin}: {rec} (net score: {net:+d})")
        lines.append(f"  Strategies: {strats}")
        for reason in r["reasons"][:3]:
            lines.append(f"  • {reason}")

    return "\n".join(lines)


# ─── CLI Test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Test with mock data
    funding = {
        "BTC": {"funding_rate": 0.015, "funding_annual": 16.4},
        "ETH": {"funding_rate": -0.012, "funding_annual": -13.1},
        "SOL": {"funding_rate": 0.003, "funding_annual": 3.3},
    }
    print("=== Funding Extreme Signals ===")
    for s in analyze_funding_extremes(funding):
        print(f"  {s['coin']}: {s['signal']} strength={s['strength']} — {s['reason']}")
