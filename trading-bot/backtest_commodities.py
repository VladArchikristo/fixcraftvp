#!/usr/bin/env python3
"""
Бэктест BTC-Neutral Mean Reversion на WTI нефти и GOLD — 7 месяцев.
Сравниваем с крипто-монетами из предыдущего теста.
"""
import sys
import time
import math
import requests
import statistics
from datetime import datetime, timezone

HL_INFO_URL = "https://api.hyperliquid.xyz/info"
HL_TIMEOUT = 20
_session = requests.Session()
_session.headers.update({"Content-Type": "application/json"})

INITIAL_BALANCE = 1000.0
LEVERAGE = 3
POSITION_PCT = 0.15
SL_PCT = 0.03
TP_PCT = 0.08
MAX_HOLD_DAYS = 7
FEE_PCT = 0.001

# Тестируем товары + крипту для сравнения
COMMODITIES = ["WTI", "GOLD"]
CRYPTO_COINS = ["ETH", "XRP", "AVAX"]
BTC = "BTC"

END_MS = int(datetime.now(timezone.utc).timestamp() * 1000)
START_MS = END_MS - int(7 * 30 * 24 * 3600 * 1000)


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
    return {
        "t": c.get("T") or c.get("t"),
        "o": float(c.get("o", 0) or c.get("open", 0)),
        "h": float(c.get("h", 0) or c.get("high", 0)),
        "l": float(c.get("l", 0) or c.get("low", 0)),
        "c": float(c.get("c", 0) or c.get("close", 0)),
        "v": float(c.get("v", 0) or c.get("volume", 0)),
    }


def ema(prices, period):
    if len(prices) < period:
        return [None] * len(prices)
    k = 2 / (period + 1)
    result = [None] * (period - 1)
    result.append(sum(prices[:period]) / period)
    for p in prices[period:]:
        result.append(result[-1] * (1 - k) + p * k)
    return result


def adx(highs, lows, closes, period=14):
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

    while len(adx_result) < len(closes):
        adx_result.append(adx_result[-1] if adx_result else None)
    return adx_result[:len(closes)]


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


def backtest_btc_neutral(coin, coin_candles, btc_candles):
    if len(coin_candles) < 30 or len(btc_candles) < 30:
        return []

    btc_map = {c["t"]: c["c"] for c in btc_candles}
    synced = [(c, btc_map.get(c["t"])) for c in coin_candles if btc_map.get(c["t"])]
    if len(synced) < 30:
        return []

    coin_prices = [s[0]["c"] for s in synced]
    btc_prices  = [s[1] for s in synced]
    candles_sync = [s[0] for s in synced]

    coin_ret = [math.log(coin_prices[i] / coin_prices[i-1]) for i in range(1, len(coin_prices))]
    btc_ret  = [math.log(btc_prices[i] / btc_prices[i-1]) for i in range(1, len(btc_prices))]

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

    z_scores = zscore(residuals, 20)

    closes_s = [c["c"] for c in candles_sync[21:]]
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

        adx_idx = i - 20
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
                continue

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


def aggregate(trades, name, balance=INITIAL_BALANCE):
    if not trades:
        return {
            "name": name, "trades": 0, "wins": 0, "losses": 0,
            "win_rate": 0, "profit_factor": 0, "total_pnl_pct": 0,
            "total_pnl_usd": 0, "max_dd": 0, "avg_hold": 0, "sharpe": 0,
            "trades_list": []
        }

    wins = [t for t in trades if t["pnl_pct"] > 0]
    losses = [t for t in trades if t["pnl_pct"] <= 0]

    gross_profit = sum(t["pnl_pct"] for t in wins)
    gross_loss = abs(sum(t["pnl_pct"] for t in losses))
    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    wr = len(wins) / len(trades) * 100

    eq = balance
    peak = eq
    max_dd = 0
    for t in trades:
        trade_pnl_usd = eq * POSITION_PCT * t["pnl_pct"] / 100
        eq += trade_pnl_usd
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100
        if dd > max_dd:
            max_dd = dd

    total_pnl_usd = eq - balance

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
        "total_pnl_usd": round(total_pnl_usd, 2),
        "max_dd": round(max_dd, 1),
        "avg_hold": round(avg_hold, 1),
        "sharpe": round(sharpe, 2),
        "trades_list": trades
    }


def print_stats(s, label_color="🔹"):
    sign = "+" if s["total_pnl_usd"] >= 0 else ""
    print(f"\n{label_color} {s['name']}")
    print(f"   Сделок:        {s['trades']} ({s['wins']}W / {s['losses']}L)")
    print(f"   Win Rate:      {s['win_rate']}%")
    print(f"   Profit Factor: {s['profit_factor']}")
    print(f"   Итог $:        {sign}${s['total_pnl_usd']:.2f}")
    print(f"   Макс просадка: {s['max_dd']}%")
    print(f"   Avg Hold:      {s['avg_hold']} дн")
    print(f"   Sharpe:        {s['sharpe']}")

    if s["trades_list"]:
        print(f"   Сделки:")
        for t in s["trades_list"]:
            sign_t = "✅" if t["pnl_pct"] > 0 else "❌"
            print(f"     {sign_t} {t['coin']} {t['direction'].upper()} | {t['entry_date']}→{t['exit_date']} | {t['hold_days']}дн | {t['pnl_pct']:+.1f}% | {t['exit_reason']}")


def main():
    print("=" * 65)
    print("BACKTEST: BTC-Neutral Mean Reversion — ТОВАРЫ vs КРИПТА")
    print(f"Период: {datetime.fromtimestamp(START_MS/1000, tz=timezone.utc).strftime('%Y-%m-%d')} → {datetime.fromtimestamp(END_MS/1000, tz=timezone.utc).strftime('%Y-%m-%d')}")
    print(f"Товары: {COMMODITIES} | Крипта: {CRYPTO_COINS}")
    print(f"Баланс: ${INITIAL_BALANCE} | Плечо: {LEVERAGE}x | SL: {SL_PCT*100}% | TP: {TP_PCT*100}%")
    print("=" * 65)

    print("\n📡 Загрузка данных...")
    daily_data = {}

    # BTC как эталон для нейтрализации
    print(f"  [BTC] дневные свечи...", end=" ", flush=True)
    raw = fetch_candles(BTC, "1d", START_MS, END_MS)
    daily_data[BTC] = [candle_to_dict(c) for c in raw]
    print(f"{len(daily_data[BTC])} свечей")

    all_coins = COMMODITIES + CRYPTO_COINS
    available = []

    for coin in all_coins:
        print(f"  [{coin}] дневные свечи...", end=" ", flush=True)
        raw = fetch_candles(coin, "1d", START_MS, END_MS)
        daily_data[coin] = [candle_to_dict(c) for c in raw]
        count = len(daily_data[coin])
        print(f"{count} свечей", end="")
        if count < 30:
            print(f" ⚠️  НЕДОСТАТОЧНО ДАННЫХ — пропускаем")
        else:
            print()
            available.append(coin)

    if not daily_data[BTC]:
        print("❌ Не удалось загрузить данные BTC — выход")
        sys.exit(1)

    print(f"\n✅ Доступно монет: {available}")

    # ─── BTC-NEUTRAL ──────────────────────────────────────────────
    print("\n\n📊 BTC-Neutral Mean Reversion: ТОВАРЫ")
    print("-" * 50)
    commodity_trades = []
    commodity_per_coin = {}
    for coin in COMMODITIES:
        if coin not in available:
            print(f"  [{coin}] — нет данных, пропущено")
            continue
        trades = backtest_btc_neutral(coin, daily_data[coin], daily_data[BTC])
        commodity_per_coin[coin] = trades
        commodity_trades.extend(trades)
        wins = len([t for t in trades if t["pnl_pct"] > 0])
        total_pnl = sum(t["pnl_pct"] for t in trades)
        print(f"  {coin}: {len(trades)} сделок | {wins}W/{len(trades)-wins}L | PnL: {total_pnl:+.1f}%")

    print("\n📊 BTC-Neutral Mean Reversion: КРИПТА (для сравнения)")
    print("-" * 50)
    crypto_trades = []
    crypto_per_coin = {}
    for coin in CRYPTO_COINS:
        if coin not in available:
            print(f"  [{coin}] — нет данных, пропущено")
            continue
        trades = backtest_btc_neutral(coin, daily_data[coin], daily_data[BTC])
        crypto_per_coin[coin] = trades
        crypto_trades.extend(trades)
        wins = len([t for t in trades if t["pnl_pct"] > 0])
        total_pnl = sum(t["pnl_pct"] for t in trades)
        print(f"  {coin}: {len(trades)} сделок | {wins}W/{len(trades)-wins}L | PnL: {total_pnl:+.1f}%")

    # ─── ИТОГОВЫЙ ОТЧЁТ ───────────────────────────────────────────
    print("\n\n" + "=" * 65)
    print("📋 ИТОГОВЫЙ ОТЧЁТ: ТОВАРЫ vs КРИПТА")
    print("=" * 65)

    commodity_stats = aggregate(commodity_trades, "ТОВАРЫ (WTI + GOLD)")
    crypto_stats = aggregate(crypto_trades, "КРИПТА (ETH + XRP + AVAX)")

    print_stats(commodity_stats, "🛢️ ")
    print()
    print_stats(crypto_stats, "🔷")

    # Детальный отчёт по каждой монете
    print("\n\n" + "=" * 65)
    print("📋 ДЕТАЛИ ПО КАЖДОМУ ИНСТРУМЕНТУ")
    print("=" * 65)

    all_results = []
    for coin in COMMODITIES:
        if coin in commodity_per_coin:
            s = aggregate(commodity_per_coin[coin], coin)
            all_results.append(s)
    for coin in CRYPTO_COINS:
        if coin in crypto_per_coin:
            s = aggregate(crypto_per_coin[coin], coin)
            all_results.append(s)

    # Сортировка по PnL
    all_results.sort(key=lambda x: x["total_pnl_usd"], reverse=True)

    for s in all_results:
        icon = "🛢️ " if s["name"] in COMMODITIES else "🔷"
        print_stats(s, icon)

    # Сводная таблица
    print("\n\n" + "=" * 65)
    print("📊 СВОДНАЯ ТАБЛИЦА (сортировка по Sharpe)")
    print("=" * 65)
    print(f"{'Инструмент':<12} {'Сделок':>7} {'Win%':>7} {'PF':>6} {'$PnL':>9} {'MaxDD':>7} {'Sharpe':>8}")
    print("-" * 65)

    all_results.sort(key=lambda x: x["sharpe"], reverse=True)
    for s in all_results:
        tag = "🛢️" if s["name"] in COMMODITIES else "🔷"
        sign = "+" if s["total_pnl_usd"] >= 0 else ""
        print(f"{tag}{s['name']:<10} {s['trades']:>7} {s['win_rate']:>6.1f}% {s['profit_factor']:>6.2f} {sign}${s['total_pnl_usd']:>7.2f} {s['max_dd']:>6.1f}% {s['sharpe']:>8.2f}")

    print("\n" + "=" * 65)
    print("✅ Бэктест завершён")


if __name__ == "__main__":
    main()
