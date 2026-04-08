#!/usr/bin/env python3
"""
Technical Analysis Engine для Василия.
Рассчитывает индикаторы из свечных данных Hyperliquid.
Не зависит от внешних TA-библиотек — всё считает сам.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("vasily_ta")


# ─── Вспомогательные ─────────────────────────────────────────────────────────

def _sma(values: list[float], period: int) -> list[float]:
    """Simple Moving Average."""
    result = []
    for i in range(len(values)):
        if i < period - 1:
            result.append(None)
        else:
            result.append(sum(values[i - period + 1:i + 1]) / period)
    return result


def _ema(values: list[float], period: int) -> list[float]:
    """Exponential Moving Average."""
    if not values:
        return []
    k = 2 / (period + 1)
    result = [None] * (period - 1)
    # Seed with SMA
    seed = sum(values[:period]) / period
    result.append(seed)
    prev = seed
    for i in range(period, len(values)):
        val = values[i] * k + prev * (1 - k)
        result.append(val)
        prev = val
    return result


# ─── RSI ─────────────────────────────────────────────────────────────────────

def calc_rsi(closes: list[float], period: int = 14) -> Optional[float]:
    """Calculate RSI from closing prices. Returns 0-100 or None."""
    if len(closes) < period + 1:
        return None

    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(c, 0) for c in changes]
    losses = [max(-c, 0) for c in changes]

    # Wilder's smoothed average
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


# ─── MACD ────────────────────────────────────────────────────────────────────

def calc_macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Optional[dict]:
    """Calculate MACD. Returns {macd, signal, histogram, trend}."""
    if len(closes) < slow + signal:
        return None

    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)

    # MACD line = EMA(fast) - EMA(slow)
    macd_line = []
    for i in range(len(closes)):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            macd_line.append(ema_fast[i] - ema_slow[i])
        else:
            macd_line.append(None)

    # Filter None values for signal calculation
    macd_valid = [v for v in macd_line if v is not None]
    if len(macd_valid) < signal:
        return None

    signal_line = _ema(macd_valid, signal)

    current_macd = macd_valid[-1]
    current_signal = signal_line[-1] if signal_line[-1] is not None else 0
    histogram = current_macd - current_signal

    # Trend detection
    prev_histogram = 0
    if len(macd_valid) >= 2 and len(signal_line) >= 2:
        prev_signal = signal_line[-2] if signal_line[-2] is not None else 0
        prev_histogram = macd_valid[-2] - prev_signal

    if histogram > 0 and prev_histogram <= 0:
        trend = "BULLISH_CROSS"
    elif histogram < 0 and prev_histogram >= 0:
        trend = "BEARISH_CROSS"
    elif histogram > 0:
        trend = "BULLISH"
    else:
        trend = "BEARISH"

    return {
        "macd": round(current_macd, 4),
        "signal": round(current_signal, 4),
        "histogram": round(histogram, 4),
        "trend": trend,
    }


# ─── Bollinger Bands ─────────────────────────────────────────────────────────

def calc_bollinger(closes: list[float], period: int = 20, std_dev: float = 2.0) -> Optional[dict]:
    """Calculate Bollinger Bands. Returns {upper, middle, lower, width, position}."""
    if len(closes) < period:
        return None

    recent = closes[-period:]
    middle = sum(recent) / period

    variance = sum((x - middle) ** 2 for x in recent) / period
    std = variance ** 0.5

    upper = middle + std_dev * std
    lower = middle - std_dev * std

    # Band width (normalized)
    width = ((upper - lower) / middle) * 100 if middle > 0 else 0

    # Current price position within bands (0 = lower, 1 = upper)
    current = closes[-1]
    band_range = upper - lower
    position = (current - lower) / band_range if band_range > 0 else 0.5

    # Interpretation
    if position > 0.95:
        zone = "OVERBOUGHT"
    elif position < 0.05:
        zone = "OVERSOLD"
    elif position > 0.8:
        zone = "UPPER"
    elif position < 0.2:
        zone = "LOWER"
    else:
        zone = "MIDDLE"

    return {
        "upper": round(upper, 2),
        "middle": round(middle, 2),
        "lower": round(lower, 2),
        "width": round(width, 2),
        "position": round(position, 3),
        "zone": zone,
    }


# ─── ATR (Average True Range) ───────────────────────────────────────────────

def calc_atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> Optional[dict]:
    """Calculate ATR for dynamic SL/TP sizing. Returns {atr, atr_pct, volatility_level}."""
    if len(closes) < period + 1:
        return None

    true_ranges = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )
        true_ranges.append(tr)

    if len(true_ranges) < period:
        return None

    # Wilder's smoothed ATR
    atr = sum(true_ranges[:period]) / period
    for i in range(period, len(true_ranges)):
        atr = (atr * (period - 1) + true_ranges[i]) / period

    current_price = closes[-1]
    atr_pct = (atr / current_price) * 100 if current_price > 0 else 0

    # Classify volatility
    if atr_pct > 5:
        level = "EXTREME"
    elif atr_pct > 3:
        level = "HIGH"
    elif atr_pct > 1.5:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "atr": round(atr, 4),
        "atr_pct": round(atr_pct, 2),
        "volatility_level": level,
    }


# ─── ADX (Average Directional Index) ───────────────────────────────────────

def calc_adx(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> Optional[dict]:
    """Calculate ADX — trend strength indicator.
    ADX > 25 = strong trend, ADX < 20 = sideways/weak.
    Returns {adx, plus_di, minus_di, trend_strength}.
    """
    if len(closes) < period * 2 + 1:
        return None

    # Step 1: Calculate +DM, -DM, TR
    plus_dm_list = []
    minus_dm_list = []
    tr_list = []

    for i in range(1, len(closes)):
        high_diff = highs[i] - highs[i - 1]
        low_diff = lows[i - 1] - lows[i]

        plus_dm = high_diff if high_diff > low_diff and high_diff > 0 else 0
        minus_dm = low_diff if low_diff > high_diff and low_diff > 0 else 0

        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )
        plus_dm_list.append(plus_dm)
        minus_dm_list.append(minus_dm)
        tr_list.append(tr)

    if len(tr_list) < period:
        return None

    # Step 2: Wilder's smoothed averages
    smoothed_plus_dm = sum(plus_dm_list[:period])
    smoothed_minus_dm = sum(minus_dm_list[:period])
    smoothed_tr = sum(tr_list[:period])

    dx_list = []

    for i in range(period, len(tr_list)):
        smoothed_plus_dm = smoothed_plus_dm - (smoothed_plus_dm / period) + plus_dm_list[i]
        smoothed_minus_dm = smoothed_minus_dm - (smoothed_minus_dm / period) + minus_dm_list[i]
        smoothed_tr = smoothed_tr - (smoothed_tr / period) + tr_list[i]

        if smoothed_tr == 0:
            continue

        plus_di = (smoothed_plus_dm / smoothed_tr) * 100
        minus_di = (smoothed_minus_dm / smoothed_tr) * 100

        di_sum = plus_di + minus_di
        if di_sum == 0:
            continue

        dx = abs(plus_di - minus_di) / di_sum * 100
        dx_list.append(dx)

    if len(dx_list) < period:
        return None

    # Step 3: ADX = smoothed average of DX
    adx = sum(dx_list[:period]) / period
    for i in range(period, len(dx_list)):
        adx = (adx * (period - 1) + dx_list[i]) / period

    # Final DI values
    final_plus_di = (smoothed_plus_dm / smoothed_tr) * 100 if smoothed_tr > 0 else 0
    final_minus_di = (smoothed_minus_dm / smoothed_tr) * 100 if smoothed_tr > 0 else 0

    # Classify trend strength
    if adx > 40:
        trend_strength = "VERY_STRONG"
    elif adx > 25:
        trend_strength = "STRONG"
    elif adx > 20:
        trend_strength = "MODERATE"
    else:
        trend_strength = "WEAK"

    return {
        "adx": round(adx, 1),
        "plus_di": round(final_plus_di, 1),
        "minus_di": round(final_minus_di, 1),
        "trend_strength": trend_strength,
    }


# ─── Stochastic RSI ────────────────────────────────────────────────────────

def calc_stochastic_rsi(closes: list[float], rsi_period: int = 14, stoch_period: int = 14,
                         k_smooth: int = 3, d_smooth: int = 3) -> Optional[dict]:
    """Stochastic RSI — faster than regular RSI for overbought/oversold detection.
    Returns {stoch_rsi_k, stoch_rsi_d, zone}.
    """
    if len(closes) < rsi_period + stoch_period + k_smooth + 5:
        return None

    # Calculate RSI series
    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(c, 0) for c in changes]
    losses = [max(-c, 0) for c in changes]

    rsi_values = []
    avg_gain = sum(gains[:rsi_period]) / rsi_period
    avg_loss = sum(losses[:rsi_period]) / rsi_period

    for i in range(rsi_period, len(gains)):
        avg_gain = (avg_gain * (rsi_period - 1) + gains[i]) / rsi_period
        avg_loss = (avg_loss * (rsi_period - 1) + losses[i]) / rsi_period
        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100 - (100 / (1 + rs)))

    if len(rsi_values) < stoch_period:
        return None

    # Stochastic of RSI
    stoch_raw = []
    for i in range(stoch_period - 1, len(rsi_values)):
        window = rsi_values[i - stoch_period + 1:i + 1]
        low = min(window)
        high = max(window)
        if high == low:
            stoch_raw.append(50.0)
        else:
            stoch_raw.append(((rsi_values[i] - low) / (high - low)) * 100)

    if len(stoch_raw) < k_smooth:
        return None

    # %K = SMA of raw stochastic
    k_values = _sma(stoch_raw, k_smooth)
    k_valid = [v for v in k_values if v is not None]
    if len(k_valid) < d_smooth:
        return None

    # %D = SMA of %K
    d_values = _sma(k_valid, d_smooth)
    d_valid = [v for v in d_values if v is not None]

    if not k_valid or not d_valid:
        return None

    k = k_valid[-1]
    d = d_valid[-1]

    # Zone classification
    if k > 80:
        zone = "OVERBOUGHT"
    elif k < 20:
        zone = "OVERSOLD"
    elif k > 50:
        zone = "BULLISH"
    else:
        zone = "BEARISH"

    # Cross detection
    cross = "NONE"
    if len(k_valid) >= 2 and len(d_valid) >= 2:
        prev_k = k_valid[-2]
        prev_d = d_valid[-2]
        if prev_k <= prev_d and k > d:
            cross = "BULLISH_CROSS"
        elif prev_k >= prev_d and k < d:
            cross = "BEARISH_CROSS"

    return {
        "stoch_rsi_k": round(k, 1),
        "stoch_rsi_d": round(d, 1),
        "zone": zone,
        "cross": cross,
    }


# ─── EMA Trend ───────────────────────────────────────────────────────────────

def calc_ema_trend(closes: list[float]) -> Optional[dict]:
    """EMA 20/50/200 trend analysis. Returns {ema20, ema50, ema200, trend, golden_cross, death_cross}."""
    ema20 = _ema(closes, 20)
    ema50 = _ema(closes, 50)

    # EMA200 needs 200+ candles, use what we have
    ema200 = _ema(closes, min(200, len(closes) - 1)) if len(closes) > 50 else [None] * len(closes)

    current = closes[-1]
    e20 = ema20[-1] if ema20 and ema20[-1] is not None else None
    e50 = ema50[-1] if ema50 and ema50[-1] is not None else None
    e200 = ema200[-1] if ema200 and ema200[-1] is not None else None

    if e20 is None or e50 is None:
        return None

    # Trend determination
    if e200 is not None:
        if current > e20 > e50 > e200:
            trend = "STRONG_BULL"
        elif current < e20 < e50 < e200:
            trend = "STRONG_BEAR"
        elif current > e50 and e20 > e50:
            trend = "BULL"
        elif current < e50 and e20 < e50:
            trend = "BEAR"
        else:
            trend = "SIDEWAYS"
    else:
        if current > e20 > e50:
            trend = "BULL"
        elif current < e20 < e50:
            trend = "BEAR"
        else:
            trend = "SIDEWAYS"

    # Golden/Death cross detection (EMA20 crossing EMA50)
    golden_cross = False
    death_cross = False
    if len(ema20) >= 2 and len(ema50) >= 2:
        prev_e20 = ema20[-2]
        prev_e50 = ema50[-2]
        if prev_e20 is not None and prev_e50 is not None:
            if prev_e20 <= prev_e50 and e20 > e50:
                golden_cross = True
            elif prev_e20 >= prev_e50 and e20 < e50:
                death_cross = True

    return {
        "ema20": round(e20, 2),
        "ema50": round(e50, 2),
        "ema200": round(e200, 2) if e200 is not None else None,
        "trend": trend,
        "golden_cross": golden_cross,
        "death_cross": death_cross,
        "price_vs_ema20": round(((current - e20) / e20) * 100, 2),
    }


# ─── Volume Analysis ─────────────────────────────────────────────────────────

def calc_volume_profile(candles: list[dict]) -> Optional[dict]:
    """Analyze volume patterns. Returns {avg_volume, volume_trend, volume_spike}."""
    if len(candles) < 20:
        return None

    volumes = [c["volume"] for c in candles]
    closes = [c["close"] for c in candles]

    avg_20 = sum(volumes[-20:]) / 20
    avg_5 = sum(volumes[-5:]) / 5
    current_vol = volumes[-1]

    # Volume trend
    if avg_5 > avg_20 * 1.5:
        vol_trend = "SURGING"
    elif avg_5 > avg_20 * 1.1:
        vol_trend = "RISING"
    elif avg_5 < avg_20 * 0.5:
        vol_trend = "DRYING_UP"
    elif avg_5 < avg_20 * 0.9:
        vol_trend = "DECLINING"
    else:
        vol_trend = "NORMAL"

    # Volume spike detection (current vs 20-period avg)
    spike = current_vol > avg_20 * 2

    # OBV-like: volume direction
    up_vol = sum(volumes[i] for i in range(1, len(volumes)) if closes[i] > closes[i - 1])
    down_vol = sum(volumes[i] for i in range(1, len(volumes)) if closes[i] < closes[i - 1])
    total_vol = up_vol + down_vol

    buy_pct = (up_vol / total_vol * 100) if total_vol > 0 else 50

    return {
        "avg_volume_20": round(avg_20, 2),
        "current_volume": round(current_vol, 2),
        "volume_ratio": round(current_vol / avg_20, 2) if avg_20 > 0 else 0,
        "volume_trend": vol_trend,
        "volume_spike": spike,
        "buy_volume_pct": round(buy_pct, 1),
    }


# ─── Support/Resistance ─────────────────────────────────────────────────────

def calc_support_resistance(candles: list[dict], num_levels: int = 3) -> Optional[dict]:
    """Find key support and resistance levels from pivot points.
    Returns {supports: [...], resistances: [...], nearest_support, nearest_resistance}."""
    if len(candles) < 20:
        return None

    current_price = candles[-1]["close"]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]

    # Find pivot highs and lows (local extremes)
    pivot_highs = []
    pivot_lows = []
    lookback = 3

    for i in range(lookback, len(candles) - lookback):
        # Pivot high: higher than surrounding candles
        if highs[i] == max(highs[i - lookback:i + lookback + 1]):
            pivot_highs.append(highs[i])
        # Pivot low: lower than surrounding candles
        if lows[i] == min(lows[i - lookback:i + lookback + 1]):
            pivot_lows.append(lows[i])

    # Cluster nearby levels
    def cluster_levels(levels: list[float], tolerance_pct: float = 0.5) -> list[float]:
        if not levels:
            return []
        levels = sorted(levels)
        clusters = []
        current_cluster = [levels[0]]
        for i in range(1, len(levels)):
            if (levels[i] - current_cluster[-1]) / current_cluster[-1] < tolerance_pct / 100:
                current_cluster.append(levels[i])
            else:
                clusters.append(sum(current_cluster) / len(current_cluster))
                current_cluster = [levels[i]]
        clusters.append(sum(current_cluster) / len(current_cluster))
        return clusters

    resistances = [r for r in cluster_levels(pivot_highs) if r > current_price]
    supports = [s for s in cluster_levels(pivot_lows) if s < current_price]

    # Take nearest levels
    resistances = sorted(resistances)[:num_levels]
    supports = sorted(supports, reverse=True)[:num_levels]

    nearest_resistance = resistances[0] if resistances else None
    nearest_support = supports[0] if supports else None

    return {
        "supports": [round(s, 2) for s in supports],
        "resistances": [round(r, 2) for r in resistances],
        "nearest_support": round(nearest_support, 2) if nearest_support else None,
        "nearest_resistance": round(nearest_resistance, 2) if nearest_resistance else None,
    }


# ─── Full Analysis ───────────────────────────────────────────────────────────

def full_analysis(candles: list[dict]) -> Optional[dict]:
    """Run all technical indicators on candle data.
    Returns comprehensive analysis dict."""
    if not candles or len(candles) < 30:
        return None

    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]

    result = {
        "rsi": calc_rsi(closes),
        "stoch_rsi": calc_stochastic_rsi(closes),
        "macd": calc_macd(closes),
        "bollinger": calc_bollinger(closes),
        "atr": calc_atr(highs, lows, closes),
        "adx": calc_adx(highs, lows, closes),
        "ema": calc_ema_trend(closes),
        "volume": calc_volume_profile(candles),
        "levels": calc_support_resistance(candles),
    }

    # Overall score: -100 (extreme bear) to +100 (extreme bull)
    score = 0
    signals = []

    # RSI contribution (-20 to +20)
    rsi = result["rsi"]
    if rsi is not None:
        if rsi > 70:
            score -= 15
            signals.append(f"RSI {rsi} overbought")
        elif rsi < 30:
            score += 15
            signals.append(f"RSI {rsi} oversold")
        elif rsi > 55:
            score += 5
        elif rsi < 45:
            score -= 5

    # MACD contribution (-25 to +25)
    macd = result["macd"]
    if macd:
        if macd["trend"] == "BULLISH_CROSS":
            score += 25
            signals.append("MACD bullish cross")
        elif macd["trend"] == "BEARISH_CROSS":
            score -= 25
            signals.append("MACD bearish cross")
        elif macd["histogram"] > 0:
            score += 10
        else:
            score -= 10

    # EMA contribution (-25 to +25)
    ema = result["ema"]
    if ema:
        if ema["trend"] == "STRONG_BULL":
            score += 25
            signals.append("Strong uptrend (price > EMA20 > EMA50 > EMA200)")
        elif ema["trend"] == "STRONG_BEAR":
            score -= 25
            signals.append("Strong downtrend")
        elif ema["trend"] == "BULL":
            score += 15
        elif ema["trend"] == "BEAR":
            score -= 15
        if ema.get("golden_cross"):
            score += 20
            signals.append("Golden Cross (EMA20 > EMA50)")
        if ema.get("death_cross"):
            score -= 20
            signals.append("Death Cross (EMA20 < EMA50)")

    # ADX contribution — trend strength filter (-15 to +15)
    adx_data = result["adx"]
    if adx_data:
        adx_val = adx_data["adx"]
        plus_di = adx_data["plus_di"]
        minus_di = adx_data["minus_di"]
        if adx_val > 25:
            # Strong trend — add directional bias
            if plus_di > minus_di:
                score += 15
                signals.append(f"ADX {adx_val} STRONG trend — bulls in control (DI+ {plus_di} > DI- {minus_di})")
            else:
                score -= 15
                signals.append(f"ADX {adx_val} STRONG trend — bears in control (DI- {minus_di} > DI+ {plus_di})")
        elif adx_val < 20:
            signals.append(f"ADX {adx_val} WEAK trend — range-bound market")

    # StochRSI contribution (-10 to +10)
    stoch = result["stoch_rsi"]
    if stoch:
        if stoch["zone"] == "OVERSOLD":
            score += 10
            signals.append(f"StochRSI {stoch['stoch_rsi_k']:.0f} OVERSOLD")
        elif stoch["zone"] == "OVERBOUGHT":
            score -= 10
            signals.append(f"StochRSI {stoch['stoch_rsi_k']:.0f} OVERBOUGHT")
        if stoch["cross"] == "BULLISH_CROSS":
            score += 10
            signals.append("StochRSI bullish cross (%K > %D)")
        elif stoch["cross"] == "BEARISH_CROSS":
            score -= 10
            signals.append("StochRSI bearish cross (%K < %D)")

    # Bollinger contribution (-15 to +15)
    bb = result["bollinger"]
    if bb:
        if bb["zone"] == "OVERSOLD":
            score += 15
            signals.append(f"Bollinger oversold (pos: {bb['position']})")
        elif bb["zone"] == "OVERBOUGHT":
            score -= 15
            signals.append(f"Bollinger overbought (pos: {bb['position']})")

    # Volume contribution (-15 to +15)
    vol = result["volume"]
    if vol:
        if vol["volume_trend"] == "SURGING" and vol["buy_volume_pct"] > 60:
            score += 15
            signals.append("Volume surging with buying pressure")
        elif vol["volume_trend"] == "SURGING" and vol["buy_volume_pct"] < 40:
            score -= 15
            signals.append("Volume surging with selling pressure")
        elif vol["volume_trend"] == "DRYING_UP":
            signals.append("Volume drying up — caution")

    result["score"] = max(-100, min(100, score))
    result["signals"] = signals

    # Overall recommendation
    if score >= 40:
        result["recommendation"] = "STRONG_BUY"
    elif score >= 15:
        result["recommendation"] = "BUY"
    elif score <= -40:
        result["recommendation"] = "STRONG_SELL"
    elif score <= -15:
        result["recommendation"] = "SELL"
    else:
        result["recommendation"] = "NEUTRAL"

    return result


def format_ta_report(coin: str, analysis: dict) -> str:
    """Format TA analysis into readable text for Claude prompt."""
    lines = [f"── {coin} Technical Analysis ──"]

    rsi = analysis.get("rsi")
    if rsi is not None:
        label = "⚠️OVERBOUGHT" if rsi > 70 else "⚠️OVERSOLD" if rsi < 30 else "neutral"
        lines.append(f"  RSI-14: {rsi} ({label})")

    macd = analysis.get("macd")
    if macd:
        lines.append(f"  MACD: {macd['macd']:.4f} | Signal: {macd['signal']:.4f} | "
                     f"Hist: {macd['histogram']:.4f} → {macd['trend']}")

    ema = analysis.get("ema")
    if ema:
        lines.append(f"  EMA: 20={ema['ema20']:.2f} 50={ema['ema50']:.2f}"
                     + (f" 200={ema['ema200']:.2f}" if ema.get("ema200") else "")
                     + f" → {ema['trend']}"
                     + (" 🔥GOLDEN CROSS" if ema.get("golden_cross") else "")
                     + (" ☠️DEATH CROSS" if ema.get("death_cross") else ""))
        lines.append(f"  Price vs EMA20: {ema['price_vs_ema20']:+.2f}%")

    bb = analysis.get("bollinger")
    if bb:
        lines.append(f"  Bollinger: [{bb['lower']:.2f} — {bb['middle']:.2f} — {bb['upper']:.2f}] "
                     f"Width: {bb['width']:.1f}% Zone: {bb['zone']}")

    atr = analysis.get("atr")
    if atr:
        lines.append(f"  ATR-14: {atr['atr']:.4f} ({atr['atr_pct']:.2f}%) Vol: {atr['volatility_level']}")

    adx = analysis.get("adx")
    if adx:
        di_arrow = "↑" if adx["plus_di"] > adx["minus_di"] else "↓"
        lines.append(f"  ADX-14: {adx['adx']:.1f} ({adx['trend_strength']}) "
                     f"DI+={adx['plus_di']:.1f} DI-={adx['minus_di']:.1f} {di_arrow}")

    stoch = analysis.get("stoch_rsi")
    if stoch:
        cross_txt = f" {stoch['cross']}" if stoch["cross"] != "NONE" else ""
        lines.append(f"  StochRSI: K={stoch['stoch_rsi_k']:.1f} D={stoch['stoch_rsi_d']:.1f} "
                     f"Zone: {stoch['zone']}{cross_txt}")

    vol = analysis.get("volume")
    if vol:
        lines.append(f"  Volume: ratio={vol['volume_ratio']:.1f}x trend={vol['volume_trend']} "
                     f"buy%={vol['buy_volume_pct']:.0f}%"
                     + (" 🚨SPIKE" if vol.get("volume_spike") else ""))

    levels = analysis.get("levels")
    if levels:
        if levels.get("nearest_support"):
            lines.append(f"  Support: {', '.join(f'${s}' for s in levels['supports'])}")
        if levels.get("nearest_resistance"):
            lines.append(f"  Resistance: {', '.join(f'${r}' for r in levels['resistances'])}")

    score = analysis.get("score", 0)
    rec = analysis.get("recommendation", "N/A")
    lines.append(f"  SCORE: {score:+d}/100 → {rec}")

    if analysis.get("signals"):
        lines.append(f"  Signals: {'; '.join(analysis['signals'])}")

    return "\n".join(lines)


# ─── CLI test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Quick test with fake data
    import random
    candles = []
    price = 100.0
    for i in range(100):
        change = random.uniform(-3, 3)
        o = price
        c = price + change
        h = max(o, c) + random.uniform(0, 2)
        l = min(o, c) - random.uniform(0, 2)
        v = random.uniform(1000, 5000)
        candles.append({"open": o, "high": h, "low": l, "close": c, "volume": v, "time": i})
        price = c

    result = full_analysis(candles)
    if result:
        print(format_ta_report("TEST", result))
