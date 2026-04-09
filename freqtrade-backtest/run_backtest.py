#!/usr/bin/env python3
"""
Standalone Backtester — порт стратегии Василия с pandas + TA-Lib.
Использует данные, скачанные с Hyperliquid.

Эмулирует Freqtrade: IStrategy-like скоринг, ROI, SL, max_open_trades.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import talib

# ─── Конфигурация (из backtest.py Василия) ─────────────────────────────────
COINS = ["ETH", "XRP", "AVAX", "BTC"]
INITIAL_BALANCE = 1000.0
POSITION_SIZE_PCT = 0.10       # 10% при net_score 50–69
POSITION_SIZE_HIGH_PCT = 0.20  # 20% при net_score ≥ 70
LEVERAGE = 5
SL_PCT = 0.02                  # 2% stop loss
TP_PCT = 0.04                  # 4% take profit
MAX_HOLD_HOURS = 24
COOLDOWN_HOURS = 2
NET_SCORE_THRESHOLD = 50
NET_SCORE_HIGH = 70
MAX_OPEN_TRADES = 3

DATA_DIR = Path(__file__).parent / "user_data" / "data" / "hyperliquid"
RESULTS_DIR = Path(__file__).parent / "results"


# ─── Загрузка данных ──────────────────────────────────────────────────────────

def load_candles(coin: str, timeframe: str) -> pd.DataFrame:
    """Загрузить свечи из JSON в DataFrame."""
    filepath = DATA_DIR / f"{coin}_USDT-{timeframe}.json"
    if not filepath.exists():
        print(f"  [WARN] Нет данных: {filepath}")
        return pd.DataFrame()

    with open(filepath) as f:
        data = json.load(f)

    df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.sort_values("date").reset_index(drop=True)
    return df


# ─── TA Score (точная копия нашего technical_analysis.full_analysis) ──────────

def calc_ta_score(df: pd.DataFrame) -> pd.Series:
    """Рассчитать TA-скор точно как в technical_analysis.py."""
    score = pd.Series(0.0, index=df.index)

    # RSI: -15..+15
    rsi = talib.RSI(df["close"], timeperiod=14)
    score = np.where(rsi > 70, score - 15, score)
    score = np.where(rsi < 30, score + 15, score)
    score = np.where((rsi > 55) & (rsi <= 70), score + 5, score)
    score = np.where((rsi < 45) & (rsi >= 30), score - 5, score)

    # MACD: -25..+25
    macd, macdsignal, macdhist = talib.MACD(df["close"], fastperiod=12, slowperiod=26, signalperiod=9)
    prev_hist = pd.Series(macdhist).shift(1).values
    score = np.where((macdhist > 0) & (prev_hist <= 0), score + 25, score)  # bullish cross
    score = np.where((macdhist < 0) & (prev_hist >= 0), score - 25, score)  # bearish cross
    score = np.where((macdhist > 0) & (prev_hist > 0), score + 10, score)
    score = np.where((macdhist < 0) & (prev_hist < 0), score - 10, score)

    # EMA 20/50: -25..+25
    ema20 = talib.EMA(df["close"], timeperiod=20)
    ema50 = talib.EMA(df["close"], timeperiod=50)

    score = np.where((df["close"] > ema20) & (ema20 > ema50), score + 15, score)
    score = np.where((df["close"] < ema20) & (ema20 < ema50), score - 15, score)

    # Golden/Death cross
    prev_ema20 = pd.Series(ema20).shift(1).values
    prev_ema50 = pd.Series(ema50).shift(1).values
    score = np.where((prev_ema20 <= prev_ema50) & (ema20 > ema50), score + 20, score)
    score = np.where((prev_ema20 >= prev_ema50) & (ema20 < ema50), score - 20, score)

    # ADX: -15..+15
    adx = talib.ADX(df["high"], df["low"], df["close"], timeperiod=14)
    plus_di = talib.PLUS_DI(df["high"], df["low"], df["close"], timeperiod=14)
    minus_di = talib.MINUS_DI(df["high"], df["low"], df["close"], timeperiod=14)
    score = np.where((adx > 25) & (plus_di > minus_di), score + 15, score)
    score = np.where((adx > 25) & (minus_di > plus_di), score - 15, score)

    # StochRSI: -20..+20 (зона + кросс)
    stoch_k, stoch_d = talib.STOCHRSI(df["close"], timeperiod=14, fastk_period=14, fastd_period=3, fastd_matype=0)
    score = np.where(stoch_k < 20, score + 10, score)
    score = np.where(stoch_k > 80, score - 10, score)
    prev_k = pd.Series(stoch_k).shift(1).values
    prev_d = pd.Series(stoch_d).shift(1).values
    score = np.where((prev_k <= prev_d) & (stoch_k > stoch_d), score + 10, score)
    score = np.where((prev_k >= prev_d) & (stoch_k < stoch_d), score - 10, score)

    # Bollinger: -15..+15
    bb_upper, bb_middle, bb_lower = talib.BBANDS(df["close"], timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
    bb_range = bb_upper - bb_lower
    bb_position = np.where(bb_range > 0, (df["close"] - bb_lower) / bb_range, 0.5)
    score = np.where(bb_position < 0.05, score + 15, score)
    score = np.where(bb_position > 0.95, score - 15, score)

    # Volume: -15..+15
    vol_sma5 = talib.SMA(df["volume"], timeperiod=5)
    vol_sma20 = talib.SMA(df["volume"], timeperiod=20)
    vol_ratio = np.where(vol_sma20 > 0, vol_sma5 / vol_sma20, 1)
    buy_pressure = df["close"] > df["open"]
    score = np.where((vol_ratio > 1.5) & buy_pressure, score + 15, score)
    score = np.where((vol_ratio > 1.5) & ~buy_pressure, score - 15, score)

    # Сохраняем ADX/StochRSI для validation layer
    df["_adx"] = adx
    df["_plus_di"] = plus_di
    df["_minus_di"] = minus_di
    df["_stochrsi_k"] = stoch_k

    return pd.Series(np.clip(score, -100, 100), index=df.index)


# ─── Resample 1h → 4h ────────────────────────────────────────────────────────

def resample_to_4h(df_1h: pd.DataFrame) -> pd.DataFrame:
    """Resample 1h candles to 4h."""
    df = df_1h.set_index("date").resample("4h").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna().reset_index()
    return df


# ─── MTF Score (weighted) ────────────────────────────────────────────────────

def calc_mtf_score(df_1h: pd.DataFrame, score_4h_series: pd.Series) -> pd.DataFrame:
    """
    Рассчитать weighted MTF score.
    Веса: 1h=1, 4h=2 (как в analyze_multi_timeframe).
    """
    df_1h["score_1h"] = calc_ta_score(df_1h)

    # Merge 4h scores в 1h DataFrame
    df_1h["date_4h"] = df_1h["date"].dt.floor("4h")
    score_4h_df = score_4h_series.reset_index()
    score_4h_df.columns = ["date_4h", "score_4h"]
    score_4h_df["date_4h"] = score_4h_df["date_4h"].dt.floor("4h")

    df_1h = df_1h.merge(score_4h_df, on="date_4h", how="left")
    df_1h["score_4h"] = df_1h["score_4h"].fillna(0)
    df_1h.drop(columns=["date_4h"], inplace=True)

    # Weighted score: 1h×1 + 4h×2 / 3
    df_1h["weighted_score"] = (df_1h["score_1h"] + df_1h["score_4h"] * 2) / 3
    df_1h["net_score"] = df_1h["weighted_score"].abs()

    return df_1h


# ─── Validation Layer (из strategies.py validate_signals) ──────────────────

def apply_validation(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validation rules:
    1. ADX > 30 + контртренд → блок
    2. StochRSI LONG при k>80 → блок, SHORT при k<20 → блок
    """
    direction = np.where(df["weighted_score"] > 0, "LONG", np.where(df["weighted_score"] < 0, "SHORT", "NEUTRAL"))

    # ADX blocker
    adx_block = (
        (df["_adx"] > 30) &
        (
            ((direction == "LONG") & (df["_minus_di"] > df["_plus_di"])) |
            ((direction == "SHORT") & (df["_plus_di"] > df["_minus_di"]))
        )
    )

    # StochRSI blocker
    stoch_block = (
        ((direction == "LONG") & (df["_stochrsi_k"] > 80)) |
        ((direction == "SHORT") & (df["_stochrsi_k"] < 20))
    )

    df["direction"] = direction
    df["blocked"] = adx_block | stoch_block
    df["signal_valid"] = (
        (df["net_score"] >= NET_SCORE_THRESHOLD) &
        (df["direction"] != "NEUTRAL") &
        (~df["blocked"])
    )

    return df


# ─── Симуляция ────────────────────────────────────────────────────────────────

def simulate(coin_data: dict) -> dict:
    """Запустить симуляцию торговли по всем монетам."""
    trades = []
    balance = INITIAL_BALANCE
    max_balance = INITIAL_BALANCE
    min_balance = INITIAL_BALANCE
    open_positions = {}  # coin -> {entry_price, direction, entry_idx, size_usd, sl, tp, entry_date}
    cooldowns = {}       # coin -> last_close_idx

    # Синхронизация по времени: используем пересечение дат
    all_dates = None
    for coin, df in coin_data.items():
        dates = set(df["date"])
        all_dates = dates if all_dates is None else all_dates & dates
    all_dates = sorted(all_dates)

    print(f"Симуляция: {len(all_dates)} шагов, {len(coin_data)} монет")
    print(f"Первая свеча: {all_dates[0]}")
    print(f"Последняя свеча: {all_dates[-1]}")
    print()

    # Нужно минимум 200 свечей для прогрева индикаторов
    warmup = 200

    for step, dt in enumerate(all_dates):
        if step < warmup:
            continue

        for coin, df in coin_data.items():
            row_mask = df["date"] == dt
            if not row_mask.any():
                continue
            row = df[row_mask].iloc[0]
            coin_idx = row.name

            # ── Проверить открытую позицию ──────────────────────────────
            if coin in open_positions:
                pos = open_positions[coin]
                h = row["high"]
                l = row["low"]
                c = row["close"]
                hold_hours = step - pos["entry_step"]

                exit_price = None
                exit_reason = None

                if pos["direction"] == "LONG":
                    if l <= pos["sl"]:
                        exit_price, exit_reason = pos["sl"], "SL"
                    elif h >= pos["tp"]:
                        exit_price, exit_reason = pos["tp"], "TP"
                elif pos["direction"] == "SHORT":
                    if h >= pos["sl"]:
                        exit_price, exit_reason = pos["sl"], "SL"
                    elif l <= pos["tp"]:
                        exit_price, exit_reason = pos["tp"], "TP"

                if exit_price is None and hold_hours >= MAX_HOLD_HOURS:
                    exit_price, exit_reason = c, "TIMEOUT"

                if exit_price is not None:
                    dir_mult = 1 if pos["direction"] == "LONG" else -1
                    pnl = ((exit_price - pos["entry_price"]) / pos["entry_price"]) * pos["size_usd"] * LEVERAGE * dir_mult
                    balance += pnl
                    max_balance = max(max_balance, balance)
                    min_balance = min(min_balance, balance)

                    trades.append({
                        "coin": coin,
                        "direction": pos["direction"],
                        "entry_price": pos["entry_price"],
                        "exit_price": exit_price,
                        "entry_date": pos["entry_date"].strftime("%d.%m.%Y %H:%M"),
                        "exit_date": dt.strftime("%d.%m.%Y %H:%M"),
                        "hold_hours": hold_hours,
                        "pnl": round(pnl, 4),
                        "exit_reason": exit_reason,
                        "balance_after": round(balance, 4),
                        "net_score": round(pos["net_score"], 1),
                    })
                    del open_positions[coin]
                    cooldowns[coin] = step
                continue

            # ── Cooldown ─────────────────────────────────────────────────
            if coin in cooldowns and (step - cooldowns[coin]) < COOLDOWN_HOURS:
                continue

            # ── Max open trades ──────────────────────────────────────────
            if len(open_positions) >= MAX_OPEN_TRADES:
                continue

            # ── Проверить сигнал ─────────────────────────────────────────
            if not row.get("signal_valid", False):
                continue

            direction = row["direction"]
            net_score = row["net_score"]
            entry_price = row["close"]
            if entry_price <= 0:
                continue

            # Динамическая позиция
            size_pct = POSITION_SIZE_HIGH_PCT if net_score >= NET_SCORE_HIGH else POSITION_SIZE_PCT
            size_usd = balance * size_pct

            # SL/TP
            sl_dist = entry_price * SL_PCT
            tp_dist = entry_price * TP_PCT
            if direction == "LONG":
                sl, tp = entry_price - sl_dist, entry_price + tp_dist
            else:
                sl, tp = entry_price + sl_dist, entry_price - tp_dist

            open_positions[coin] = {
                "entry_price": entry_price,
                "direction": direction,
                "entry_step": step,
                "entry_date": dt,
                "size_usd": size_usd,
                "sl": sl,
                "tp": tp,
                "net_score": net_score,
            }

    # Закрыть оставшиеся позиции
    for coin, pos in open_positions.items():
        df = coin_data[coin]
        last_row = df.iloc[-1]
        exit_price = last_row["close"]
        dir_mult = 1 if pos["direction"] == "LONG" else -1
        pnl = ((exit_price - pos["entry_price"]) / pos["entry_price"]) * pos["size_usd"] * LEVERAGE * dir_mult
        balance += pnl
        max_balance = max(max_balance, balance)

        trades.append({
            "coin": coin,
            "direction": pos["direction"],
            "entry_price": pos["entry_price"],
            "exit_price": exit_price,
            "entry_date": pos["entry_date"].strftime("%d.%m.%Y %H:%M"),
            "exit_date": last_row["date"].strftime("%d.%m.%Y %H:%M"),
            "hold_hours": len(all_dates) - pos["entry_step"],
            "pnl": round(pnl, 4),
            "exit_reason": "END_OF_DATA",
            "balance_after": round(balance, 4),
            "net_score": round(pos["net_score"], 1),
        })

    return {
        "trades": trades,
        "final_balance": balance,
        "max_balance": max_balance,
        "min_balance": min_balance,
    }


# ─── Статистика ───────────────────────────────────────────────────────────────

def print_results(result: dict):
    """Вывести красивый отчёт."""
    trades = result["trades"]
    balance = result["final_balance"]
    max_bal = result["max_balance"]
    min_bal = result["min_balance"]

    total = len(trades)
    winning = [t for t in trades if t["pnl"] > 0]
    losing = [t for t in trades if t["pnl"] <= 0]

    win_rate = len(winning) / total * 100 if total > 0 else 0
    total_pnl = balance - INITIAL_BALANCE
    total_pnl_pct = (total_pnl / INITIAL_BALANCE) * 100
    max_dd_pct = ((max_bal - min_bal) / max_bal * 100) if max_bal > 0 else 0

    avg_win = sum(t["pnl"] for t in winning) / len(winning) if winning else 0
    avg_loss = sum(t["pnl"] for t in losing) / len(losing) if losing else 0

    gross_profit = sum(t["pnl"] for t in winning)
    gross_loss = abs(sum(t["pnl"] for t in losing))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

    # По exit_reason
    reason_counts = {}
    for t in trades:
        r = t["exit_reason"]
        reason_counts[r] = reason_counts.get(r, 0) + 1

    # По монетам
    coin_stats = {}
    for t in trades:
        c = t["coin"]
        if c not in coin_stats:
            coin_stats[c] = {"trades": 0, "wins": 0, "pnl": 0.0}
        coin_stats[c]["trades"] += 1
        coin_stats[c]["pnl"] += t["pnl"]
        if t["pnl"] > 0:
            coin_stats[c]["wins"] += 1

    # По направлению
    long_trades = [t for t in trades if t["direction"] == "LONG"]
    short_trades = [t for t in trades if t["direction"] == "SHORT"]
    long_wins = len([t for t in long_trades if t["pnl"] > 0])
    short_wins = len([t for t in short_trades if t["pnl"] > 0])

    best_trade = max(trades, key=lambda x: x["pnl"]) if trades else None
    worst_trade = min(trades, key=lambda x: x["pnl"]) if trades else None

    # Средняя длительность
    avg_hold = sum(t["hold_hours"] for t in trades) / total if total > 0 else 0

    print()
    print("=" * 65)
    print("   VASILY MTF BACKTEST — TA-Lib + Hyperliquid Data")
    print("=" * 65)
    print()
    print(f"  Стартовый баланс:  ${INITIAL_BALANCE:.0f}")
    print(f"  Финальный баланс:  ${balance:.2f}")
    sign = "+" if total_pnl >= 0 else ""
    print(f"  Общий P&L:         {sign}${total_pnl:.2f} ({sign}{total_pnl_pct:.1f}%)")
    print(f"  Макс просадка:     {max_dd_pct:.1f}%")
    print()
    print("─── TRADES ───────────────────────────────────────────")
    print(f"  Всего сделок:   {total}")
    print(f"  Прибыльных:     {len(winning)} ({win_rate:.1f}%)")
    print(f"  Убыточных:      {len(losing)}")
    print(f"  Profit Factor:  {profit_factor:.2f}")
    print(f"  Avg Win:        +${avg_win:.2f}")
    print(f"  Avg Loss:       ${avg_loss:.2f}")
    print(f"  Avg Hold:       {avg_hold:.1f}h")
    print()
    print("─── НАПРАВЛЕНИЕ ──────────────────────────────────────")
    print(f"  LONG:  {len(long_trades)} trades, {long_wins} wins ({long_wins/max(1,len(long_trades))*100:.0f}%)")
    print(f"  SHORT: {len(short_trades)} trades, {short_wins} wins ({short_wins/max(1,len(short_trades))*100:.0f}%)")
    print()
    print("─── EXIT REASONS ─────────────────────────────────────")
    for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
        print(f"  {reason:15s}: {count} ({count/total*100:.0f}%)")
    print()
    print("─── ПО МОНЕТАМ ───────────────────────────────────────")
    for coin, cs in sorted(coin_stats.items(), key=lambda x: -x[1]["pnl"]):
        wr = cs["wins"] / cs["trades"] * 100 if cs["trades"] > 0 else 0
        s = "+" if cs["pnl"] >= 0 else ""
        print(f"  {coin:5s}: {cs['trades']:3d} сделок, WR {wr:5.1f}%, P&L {s}${cs['pnl']:.2f}")

    print()
    if best_trade:
        print(f"  Лучшая:  {best_trade['coin']} {best_trade['direction']} "
              f"{best_trade['entry_date'][:10]} → +${best_trade['pnl']:.2f} (score={best_trade['net_score']})")
    if worst_trade:
        print(f"  Худшая:  {worst_trade['coin']} {worst_trade['direction']} "
              f"{worst_trade['entry_date'][:10]} → ${worst_trade['pnl']:.2f} (score={worst_trade['net_score']})")
    print("=" * 65)

    return {
        "total_trades": total,
        "win_rate": round(win_rate, 2),
        "profit_factor": round(profit_factor, 4) if profit_factor != float("inf") else None,
        "total_pnl": round(total_pnl, 4),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "final_balance": round(balance, 4),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "coin_stats": coin_stats,
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("Загружаю данные...")
    coin_data = {}

    for coin in COINS:
        print(f"  {coin}: ", end="")
        df_1h = load_candles(coin, "1h")
        if df_1h.empty:
            continue

        # Resample to 4h
        df_4h = resample_to_4h(df_1h)
        print(f"1h={len(df_1h)}, 4h={len(df_4h)} свечей")

        # Score 4h
        if len(df_4h) >= 60:
            score_4h = calc_ta_score(df_4h)
            score_4h.index = df_4h["date"]
        else:
            score_4h = pd.Series(dtype=float)

        # MTF score на 1h
        df_1h = calc_mtf_score(df_1h, score_4h)

        # Validation layer
        df_1h = apply_validation(df_1h)

        coin_data[coin] = df_1h

    if not coin_data:
        print("Нет данных для бэктеста!")
        return

    print()

    # Симуляция
    result = simulate(coin_data)

    # Результаты
    summary = print_results(result)

    # Сохранить
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "backtest_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "config": {
                "coins": COINS,
                "initial_balance": INITIAL_BALANCE,
                "position_size_pct": POSITION_SIZE_PCT,
                "position_size_high_pct": POSITION_SIZE_HIGH_PCT,
                "leverage": LEVERAGE,
                "sl_pct": SL_PCT,
                "tp_pct": TP_PCT,
                "max_hold_hours": MAX_HOLD_HOURS,
                "net_score_threshold": NET_SCORE_THRESHOLD,
                "max_open_trades": MAX_OPEN_TRADES,
            },
            "summary": summary,
            "trades": result["trades"],
        }, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nРезультаты сохранены: {out_path}")


if __name__ == "__main__":
    main()
