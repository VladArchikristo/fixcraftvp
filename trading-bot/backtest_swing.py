#!/usr/bin/env python3
"""
Бэктест свинг-стратегий для Васи — 7 месяцев на Hyperliquid.
Стратегии:
  1. EMA Trend Following (дневной таймфрейм)
  2. Liquidation Cascade Swing (объёмные шипы + откат)
  3. BTC-Neutral Mean Reversion (Z-score остатков)
"""
import sys
import time
import math
import requests
import statistics
from datetime import datetime, timezone, timedelta

HL_INFO_URL = "https://api.hyperliquid.xyz/info"
HL_TIMEOUT = 20
_session = requests.Session()
_session.headers.update({"Content-Type": "application/json"})

# ─── КОНФИГ БЭКТЕСТА ──────────────────────────────────────────────────────────
INITIAL_BALANCE = 1000.0
LEVERAGE = 3                # Свинг — меньше плечо
POSITION_PCT = 0.15         # 15% от баланса на сделку
SL_PCT = 0.03               # 3% stop loss
TP_PCT = 0.08               # 8% take profit (свинг ждёт больше)
MAX_HOLD_DAYS = 7
FEE_PCT = 0.001             # 0.1% комиссия (maker)

COINS = ["ETH", "XRP", "AVAX"]
BTC = "BTC"

# 7 месяцев назад от сегодня
END_MS = int(datetime.now(timezone.utc).timestamp() * 1000)
START_MS = END_MS - int(7 * 30 * 24 * 3600 * 1000)  # ~7 месяцев


def _post(payload, retries=3):
    for attempt in range(retries):
        try:
            r = _session.post(HL_INFO_URL, json=payload, timeout=HL_TIMEOUT)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                return None


def fetch_candles(coin, interval="1d", start_ms=None, end_ms=None):
    """Загрузить дневные свечи с пагинацией."""
    interval_ms = {"1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
    step = interval_ms.get(interval, 86_400_000) * 500

    all_c = []
    cursor = start_ms or START_MS
    end = end_ms or END_MS

    while cursor < end:
        chunk_end = min(cursor + step, end)
        data = _post({
            "type": "candleSnapshot",
            "req": {"coin": coin, "interval": interval,
                    "startTime": cursor, "endTime": chunk_end}
        })
        if data:
            all_c.extend(data)
        cursor = chunk_end
        time.sleep(0.15)

    # Дедупликация и сортировка
    seen = set()
    result = []
    for c in all_c:
        t = c.get("T") or c.get("t")
        if t and t not in seen:
            seen.add(t)
            result.append(c)
    result.sort(key=lambda x: x.get("T") or x.get("t"))
    return result


def candle_to_dict(c):
    """Нормализовать свечу."""
    return {
        "t": c.get("T") or c.get("t"),
        "o": float(c.get("o", 0) or c.get("open", 0)),
        "h": float(c.get("h", 0) or c.get("high", 0)),
        "l": float(c.get("l", 0) or c.get("low", 0)),
        "c": float(c.get("c", 0) or c.get("close", 0)),
        "v": float(c.get("v", 0) or c.get("volume", 0)),
    }


def ema(prices, period):
    """Exponential Moving Average."""
    if len(prices) < period:
        return [None] * len(prices)
    k = 2 / (period + 1)
    result = [None] * (period - 1)
    result.append(sum(prices[:period]) / period)
    for p in prices[period:]:
        result.append(result[-1] * (1 - k) + p * k)
    return result


def sma(prices, period):
    result = []
    for i in range(len(prices)):
        if i < period - 1:
            result.append(None)
        else:
            result.append(sum(prices[i - period + 1:i + 1]) / period)
    return result


def adx(highs, lows, closes, period=14):
    """ADX calculation."""
    if len(closes) < period * 2:
        return [None] * len(closes)

    tr_list, pdm_list, ndm_list = [], [], []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i],
                 abs(highs[i] - closes[i-1]),
                 abs(lows[i] - closes[i-1]))
        up_move = highs[i] - highs[i-1]
        down_move = lows[i-1] - lows[i]
        pdm_list.append(up_move if up_move > down_move and up_move > 0 else 0)
        ndm_list.append(down_move if down_move > up_move and down_move > 0 else 0)
        tr_list.append(tr)

    def smooth(lst, p):
        r = [None] * (p - 1)
        r.append(sum(lst[:p]))
        for v in lst[p:]:
            r.append(r[-1] - r[-1] / p + v)
        return r

    atr_s = smooth(tr_list, period)
    pdi_s = smooth(pdm_list, period)
    ndi_s = smooth(ndm_list, period)

    dx_list = []
    for i in range(len(atr_s)):
        if atr_s[i] and atr_s[i] > 0:
            pdi = 100 * pdi_s[i] / atr_s[i]
            ndi = 100 * ndi_s[i] / atr_s[i]
            dx = 100 * abs(pdi - ndi) / (pdi + ndi) if (pdi + ndi) > 0 else 0
            dx_list.append(dx)
        else:
            dx_list.append(None)

    adx_result = [None] * period
    valid_dx = [x for x in dx_list if x is not None]
    if len(valid_dx) >= period:
        adx_val = sum(valid_dx[:period]) / period
        adx_result.append(adx_val)
        for dx in valid_dx[period:]:
            adx_val = (adx_val * (period - 1) + dx) / period
            adx_result.append(adx_val)

    # Выровнять длину
    while len(adx_result) < len(closes):
        adx_result.append(adx_result[-1] if adx_result else None)
    return adx_result[:len(closes)]


def rsi(closes, period=14):
    if len(closes) < period + 1:
        return [None] * len(closes)
    result = [None] * period
    gains = [max(closes[i] - closes[i-1], 0) for i in range(1, len(closes))]
    losses = [max(closes[i-1] - closes[i], 0) for i in range(1, len(closes))]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(closes) - 1):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        result.append(100 - 100 / (1 + rs))
    return result


def zscore(series, period=20):
    result = [None] * len(series)
    for i in range(period, len(series)):
        window = series[i - period:i]
        if None in window:
            continue
        mean = sum(window) / len(window)
        std = statistics.stdev(window)
        if std > 0:
            result[i] = (series[i] - mean) / std
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# СТРАТЕГИЯ 1: EMA Trend Following
# ═══════════════════════════════════════════════════════════════════════════════

def backtest_ema_trend(coin, candles):
    """
    EMA 21/50 на дневке.
    Вход: EMA21 > EMA50 (golden cross), RSI 45-65, ADX > 25
    Выход: EMA21 пробивает EMA50 вниз или TP/SL
    """
    if len(candles) < 60:
        return []

    closes = [c["c"] for c in candles]
    highs  = [c["h"] for c in candles]
    lows   = [c["l"] for c in candles]

    ema21 = ema(closes, 21)
    ema50 = ema(closes, 50)
    rsi14 = rsi(closes, 14)
    adx14 = adx(highs, lows, closes, 14)

    trades = []
    in_trade = False
    entry_price = 0
    entry_idx = 0
    direction = "long"

    min_len = min(len(ema21), len(ema50), len(rsi14), len(adx14), len(candles))
    for i in range(55, min_len):
        if None in [ema21[i], ema50[i], rsi14[i], adx14[i]]:
            continue

        price = closes[i]

        if in_trade:
            hold_days = i - entry_idx
            pnl_pct = (price - entry_price) / entry_price if direction == "long" else (entry_price - price) / entry_price

            # Выход по SL / TP / EMA cross / MAX HOLD
            exit_reason = None
            if pnl_pct <= -SL_PCT:
                exit_reason = "SL"
            elif pnl_pct >= TP_PCT:
                exit_reason = "TP"
            elif hold_days >= MAX_HOLD_DAYS:
                exit_reason = "TIMEOUT"
            elif direction == "long" and ema21[i] < ema50[i]:
                exit_reason = "EMA_CROSS"
            elif direction == "short" and ema21[i] > ema50[i]:
                exit_reason = "EMA_CROSS"

            if exit_reason:
                gross_pnl = pnl_pct * LEVERAGE
                net_pnl = gross_pnl - FEE_PCT * 2
                trades.append({
                    "coin": coin,
                    "entry_date": datetime.fromtimestamp(candles[entry_idx]["t"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d"),
                    "exit_date": datetime.fromtimestamp(candles[i]["t"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d"),
                    "direction": direction,
                    "hold_days": hold_days,
                    "pnl_pct": round(net_pnl * 100, 2),
                    "exit_reason": exit_reason,
                })
                in_trade = False
        else:
            # Сигнал на вход LONG
            if (ema21[i] > ema50[i] and
                    ema21[i-1] <= ema50[i-1] and  # свежий cross
                    45 <= rsi14[i] <= 65 and
                    adx14[i] > 25):
                in_trade = True
                direction = "long"
                entry_price = price
                entry_idx = i

            # Сигнал на вход SHORT (инверсный)
            elif (ema21[i] < ema50[i] and
                    ema21[i-1] >= ema50[i-1] and
                    35 <= rsi14[i] <= 55 and
                    adx14[i] > 25):
                in_trade = True
                direction = "short"
                entry_price = price
                entry_idx = i

    return trades


# ═══════════════════════════════════════════════════════════════════════════════
# СТРАТЕГИЯ 2: Liquidation Cascade Swing
# ═══════════════════════════════════════════════════════════════════════════════

def backtest_liquidation_cascade(coin, candles_1h):
    """
    Обнаружить каскадные ликвидации (объём > 3x avg + большой фитиль)
    и войти против толпы после подтверждения разворота.
    Работает на часовых данных.
    """
    if len(candles_1h) < 48:
        return []

    closes = [c["c"] for c in candles_1h]
    highs  = [c["h"] for c in candles_1h]
    lows   = [c["l"] for c in candles_1h]
    volumes = [c["v"] for c in candles_1h]

    trades = []
    in_trade = False
    entry_price = 0
    entry_idx = 0
    direction = "long"

    for i in range(48, len(candles_1h)):
        price = closes[i]
        vol_avg = sum(volumes[i-24:i]) / 24

        if in_trade:
            hold_hours = i - entry_idx
            pnl_pct = (price - entry_price) / entry_price if direction == "long" else (entry_price - price) / entry_price

            exit_reason = None
            if pnl_pct <= -SL_PCT:
                exit_reason = "SL"
            elif pnl_pct >= TP_PCT:
                exit_reason = "TP"
            elif hold_hours >= MAX_HOLD_DAYS * 24:
                exit_reason = "TIMEOUT"

            if exit_reason:
                gross_pnl = pnl_pct * LEVERAGE
                net_pnl = gross_pnl - FEE_PCT * 2
                trades.append({
                    "coin": coin,
                    "entry_date": datetime.fromtimestamp(candles_1h[entry_idx]["t"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
                    "exit_date": datetime.fromtimestamp(candles_1h[i]["t"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
                    "direction": direction,
                    "hold_days": round(hold_hours / 24, 1),
                    "pnl_pct": round(net_pnl * 100, 2),
                    "exit_reason": exit_reason,
                })
                in_trade = False
        else:
            if vol_avg == 0:
                continue

            # Паттерн: огромный объём + нижний фитиль (лонг-ликвидация каскад)
            candle_body = abs(closes[i] - candles_1h[i]["o"])
            lower_wick = candles_1h[i]["o"] - lows[i] if closes[i] > candles_1h[i]["o"] else closes[i] - lows[i]
            upper_wick = highs[i] - (closes[i] if closes[i] > candles_1h[i]["o"] else candles_1h[i]["o"])

            vol_spike = volumes[i] > vol_avg * 3

            # LONG CASCADE: цена резко вниз, фитиль снизу > тело × 2
            if (vol_spike and
                    lower_wick > candle_body * 2 and
                    closes[i] > lows[i] * 1.01 and  # закрылась выше лоу
                    closes[i] > closes[i-1] * 0.97):  # не катастрофическое закрытие
                in_trade = True
                direction = "long"
                entry_price = price
                entry_idx = i

            # SHORT CASCADE: цена резко вверх, фитиль сверху > тело × 2
            elif (vol_spike and
                    upper_wick > candle_body * 2 and
                    closes[i] < highs[i] * 0.99):
                in_trade = True
                direction = "short"
                entry_price = price
                entry_idx = i

    return trades


# ═══════════════════════════════════════════════════════════════════════════════
# СТРАТЕГИЯ 3: BTC-Neutral Mean Reversion
# ═══════════════════════════════════════════════════════════════════════════════

def backtest_btc_neutral(coin, coin_candles, btc_candles):
    """
    Вычесть BTC-бету из монеты → торговать residuals по Z-score.
    Вход: Z-score > 2 (шорт) или < -2 (лонг), ADX < 25 (боковик)
    """
    if len(coin_candles) < 30 or len(btc_candles) < 30:
        return []

    # Синхронизировать по времени
    btc_map = {c["t"]: c["c"] for c in btc_candles}
    synced = [(c, btc_map.get(c["t"])) for c in coin_candles if btc_map.get(c["t"])]
    if len(synced) < 30:
        return []

    coin_prices = [s[0]["c"] for s in synced]
    btc_prices  = [s[1] for s in synced]
    candles_sync = [s[0] for s in synced]

    # Логарифмические доходности
    coin_ret = [math.log(coin_prices[i] / coin_prices[i-1]) for i in range(1, len(coin_prices))]
    btc_ret  = [math.log(btc_prices[i] / btc_prices[i-1]) for i in range(1, len(btc_prices))]

    # Вычислить бету (скользящая регрессия 20 дней)
    residuals = []
    for i in range(20, len(coin_ret)):
        window_coin = coin_ret[i-20:i]
        window_btc  = btc_ret[i-20:i]
        mean_c = sum(window_coin) / 20
        mean_b = sum(window_btc) / 20
        cov = sum((window_coin[j] - mean_c) * (window_btc[j] - mean_b) for j in range(20)) / 20
        var_b = sum((window_btc[j] - mean_b) ** 2 for j in range(20)) / 20
        beta = cov / var_b if var_b > 0 else 0
        residuals.append(coin_ret[i] - beta * btc_ret[i])

    if len(residuals) < 20:
        return []

    # Z-score остатков
    z_scores = zscore(residuals, 20)

    # ADX на дневке
    closes_s = [c["c"] for c in candles_sync[21:]]  # +1 для residuals offset
    highs_s  = [c["h"] for c in candles_sync[21:]]
    lows_s   = [c["l"] for c in candles_sync[21:]]
    adx14 = adx(highs_s, lows_s, closes_s, 14)

    trades = []
    in_trade = False
    entry_price = 0
    entry_idx = 0
    direction = "long"

    for i in range(20, len(z_scores)):
        z = z_scores[i]
        if z is None:
            continue

        adx_idx = i - 20  # смещение
        adx_val = adx14[adx_idx] if adx_idx < len(adx14) else None
        price = candles_sync[i + 21]["c"] if i + 21 < len(candles_sync) else None
        if price is None:
            continue

        if in_trade:
            hold_days = i - entry_idx
            pnl_pct = (price - entry_price) / entry_price if direction == "long" else (entry_price - price) / entry_price

            exit_reason = None
            if pnl_pct <= -SL_PCT:
                exit_reason = "SL"
            elif pnl_pct >= TP_PCT:
                exit_reason = "TP"
            elif hold_days >= MAX_HOLD_DAYS:
                exit_reason = "TIMEOUT"
            elif direction == "long" and z > 0.5:
                exit_reason = "MEAN_REVERT"
            elif direction == "short" and z < -0.5:
                exit_reason = "MEAN_REVERT"

            if exit_reason:
                gross_pnl = pnl_pct * LEVERAGE
                net_pnl = gross_pnl - FEE_PCT * 2
                try:
                    entry_date = datetime.fromtimestamp(candles_sync[entry_idx + 21]["t"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                    exit_date  = datetime.fromtimestamp(candles_sync[i + 21]["t"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                except:
                    entry_date = exit_date = "?"
                trades.append({
                    "coin": coin,
                    "entry_date": entry_date,
                    "exit_date": exit_date,
                    "direction": direction,
                    "hold_days": hold_days,
                    "pnl_pct": round(net_pnl * 100, 2),
                    "exit_reason": exit_reason,
                })
                in_trade = False
        else:
            if adx_val is not None and adx_val > 25:
                continue  # Только боковик

            if z < -2.0:
                in_trade = True
                direction = "long"
                entry_price = price
                entry_idx = i
            elif z > 2.0:
                in_trade = True
                direction = "short"
                entry_price = price
                entry_idx = i

    return trades


# ─── АГРЕГАЦИЯ РЕЗУЛЬТАТОВ ────────────────────────────────────────────────────

def aggregate(trades, name, balance=INITIAL_BALANCE):
    if not trades:
        return {
            "name": name, "trades": 0, "win_rate": 0,
            "profit_factor": 0, "total_pnl_pct": 0,
            "total_pnl_usd": 0, "max_dd": 0, "avg_hold": 0,
            "sharpe": 0
        }

    wins = [t for t in trades if t["pnl_pct"] > 0]
    losses = [t for t in trades if t["pnl_pct"] <= 0]

    gross_profit = sum(t["pnl_pct"] for t in wins)
    gross_loss = abs(sum(t["pnl_pct"] for t in losses))
    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    wr = len(wins) / len(trades) * 100

    # Equity curve для max drawdown
    eq = balance
    peak = eq
    max_dd = 0
    pnls_usd = []
    for t in trades:
        trade_pnl_usd = eq * POSITION_PCT * t["pnl_pct"] / 100
        eq += trade_pnl_usd
        pnls_usd.append(trade_pnl_usd)
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100
        if dd > max_dd:
            max_dd = dd

    total_pnl_usd = eq - balance

    # Sharpe (упрощённый)
    avg_ret = sum(t["pnl_pct"] for t in trades) / len(trades)
    std_ret = statistics.stdev([t["pnl_pct"] for t in trades]) if len(trades) > 1 else 1
    sharpe = (avg_ret / std_ret) * math.sqrt(len(trades)) if std_ret > 0 else 0

    avg_hold = sum(t.get("hold_days", 0) for t in trades) / len(trades)

    return {
        "name": name,
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(wr, 1),
        "profit_factor": round(pf, 2),
        "total_pnl_pct": round(sum(t["pnl_pct"] for t in trades) / len(trades) * len(trades), 2),
        "total_pnl_usd": round(total_pnl_usd, 2),
        "max_dd": round(max_dd, 1),
        "avg_hold": round(avg_hold, 1),
        "sharpe": round(sharpe, 2),
        "trades_list": trades
    }


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("BACKTEST: 3 СВИНГ-СТРАТЕГИИ — 7 МЕСЯЦЕВ")
    print(f"Период: {datetime.fromtimestamp(START_MS/1000, tz=timezone.utc).strftime('%Y-%m-%d')} → {datetime.fromtimestamp(END_MS/1000, tz=timezone.utc).strftime('%Y-%m-%d')}")
    print(f"Монеты: {COINS} | Баланс: ${INITIAL_BALANCE} | Плечо: {LEVERAGE}x")
    print("=" * 60)

    # Загрузка данных
    print("\n📡 Загрузка данных...")
    daily_data = {}
    hourly_data = {}

    for coin in COINS + [BTC]:
        print(f"  [{coin}] дневные свечи...", end=" ", flush=True)
        raw = fetch_candles(coin, "1d", START_MS, END_MS)
        daily_data[coin] = [candle_to_dict(c) for c in raw]
        print(f"{len(daily_data[coin])} свечей")

        if coin != BTC:
            print(f"  [{coin}] часовые свечи...", end=" ", flush=True)
            raw_h = fetch_candles(coin, "1h", START_MS, END_MS)
            hourly_data[coin] = [candle_to_dict(c) for c in raw_h]
            print(f"{len(hourly_data[coin])} свечей")

    # ─── СТРАТЕГИЯ 1: EMA TREND ───────────────────────────────────────────────
    print("\n\n📊 СТРАТЕГИЯ 1: EMA Trend Following (дневной)")
    print("-" * 50)
    all_ema_trades = []
    for coin in COINS:
        trades = backtest_ema_trend(coin, daily_data[coin])
        all_ema_trades.extend(trades)
        wins = len([t for t in trades if t["pnl_pct"] > 0])
        print(f"  {coin}: {len(trades)} сделок | {wins} побед | PnL: {sum(t['pnl_pct'] for t in trades):.1f}%")

    ema_stats = aggregate(all_ema_trades, "EMA Trend Following")

    # ─── СТРАТЕГИЯ 2: LIQUIDATION CASCADE ────────────────────────────────────
    print("\n📊 СТРАТЕГИЯ 2: Liquidation Cascade Swing (часовой)")
    print("-" * 50)
    all_liq_trades = []
    for coin in COINS:
        trades = backtest_liquidation_cascade(coin, hourly_data[coin])
        all_liq_trades.extend(trades)
        wins = len([t for t in trades if t["pnl_pct"] > 0])
        print(f"  {coin}: {len(trades)} сделок | {wins} побед | PnL: {sum(t['pnl_pct'] for t in trades):.1f}%")

    liq_stats = aggregate(all_liq_trades, "Liquidation Cascade")

    # ─── СТРАТЕГИЯ 3: BTC-NEUTRAL MEAN REVERSION ─────────────────────────────
    print("\n📊 СТРАТЕГИЯ 3: BTC-Neutral Mean Reversion (дневной)")
    print("-" * 50)
    all_mr_trades = []
    for coin in COINS:
        trades = backtest_btc_neutral(coin, daily_data[coin], daily_data[BTC])
        all_mr_trades.extend(trades)
        wins = len([t for t in trades if t["pnl_pct"] > 0])
        print(f"  {coin}: {len(trades)} сделок | {wins} побед | PnL: {sum(t['pnl_pct'] for t in trades):.1f}%")

    mr_stats = aggregate(all_mr_trades, "BTC-Neutral Mean Reversion")

    # ─── ИТОГОВЫЙ ОТЧЁТ ───────────────────────────────────────────────────────
    print("\n")
    print("=" * 60)
    print("📋 ИТОГОВЫЙ ОТЧЁТ")
    print("=" * 60)

    for s in [ema_stats, liq_stats, mr_stats]:
        print(f"\n🔹 {s['name']}")
        print(f"   Сделок:        {s['trades']} ({s.get('wins',0)}W / {s.get('losses',0)}L)")
        print(f"   Win Rate:      {s['win_rate']}%")
        print(f"   Profit Factor: {s['profit_factor']}")
        print(f"   Итог $:        ${s['total_pnl_usd']:+.2f}")
        print(f"   Макс просадка: {s['max_dd']}%")
        print(f"   Avg Hold:      {s['avg_hold']} дней")
        print(f"   Sharpe:        {s['sharpe']}")

    # Рейтинг
    print("\n\n🏆 РЕЙТИНГ СТРАТЕГИЙ")
    print("-" * 40)
    ranked = sorted([ema_stats, liq_stats, mr_stats],
                    key=lambda x: x["total_pnl_usd"], reverse=True)
    medals = ["🥇", "🥈", "🥉"]
    for i, s in enumerate(ranked):
        print(f"  {medals[i]} {s['name']}: ${s['total_pnl_usd']:+.2f} | WR:{s['win_rate']}% | PF:{s['profit_factor']} | DD:{s['max_dd']}%")

    print("\n✅ Бэктест завершён.")
    return ema_stats, liq_stats, mr_stats


if __name__ == "__main__":
    main()
