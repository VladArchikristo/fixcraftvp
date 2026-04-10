#!/usr/bin/env python3
"""
Backtest скрипт для стратегий Василия.
Прогоняет MTF-стратегию по 3 месяцам исторических 1h-свечей.
"""
import sys
sys.path.insert(0, "/Users/vladimirprihodko/Папка тест/fixcraftvp/trading-bot")

import json
import time
import requests
from datetime import datetime, timezone
from pathlib import Path

# ─── Импорт модулей Васи ─────────────────────────────────────────────────────
from technical_analysis import full_analysis
from strategies import analyze_multi_timeframe

# ─── Конфигурация ─────────────────────────────────────────────────────────────
COINS = ["ETH", "XRP", "AVAX"]
HL_INFO_URL = "https://api.hyperliquid.xyz/info"
HL_TIMEOUT = 20
INITIAL_BALANCE = 1000.0
POSITION_SIZE_PCT = 0.10       # 10% от баланса (стандарт, net_score 50–69)
POSITION_SIZE_HIGH_PCT = 0.20  # 20% от баланса при net_score ≥ 70
LEVERAGE = 5
SL_PCT = 0.02                  # 2% stop loss (фиксированный)
TP_PCT = 0.04                  # 4% take profit (фиксированный)
MAX_HOLD_HOURS = 24
COOLDOWN_HOURS = 2
NET_SCORE_THRESHOLD = 50       # минимальный порог для входа
NET_SCORE_HIGH = 70            # порог для удвоения позиции
MIN_CANDLES_FOR_TA = 200       # минимум свечей для расчёта индикаторов

# ─── Новые фильтры ──────────────────────────────────────────────────────────
TIME_FILTER_ENABLED = False
TIME_FILTER_START_UTC = 2       # запрет торговли с 02:00 UTC
TIME_FILTER_END_UTC = 6         # ... до 06:00 UTC

VOLUME_FILTER_ENABLED = False
VOLUME_FILTER_MULTIPLIER = 1.5  # объём > среднего × 1.5
VOLUME_LOOKBACK = 20            # скользящее среднее за 20 свечей (1h)

_session = requests.Session()
_session.headers.update({"Content-Type": "application/json"})


# ─── Загрузка данных ──────────────────────────────────────────────────────────

def _post(payload: dict, retries: int = 3):
    """POST к Hyperliquid с retry."""
    for attempt in range(retries):
        try:
            resp = _session.post(HL_INFO_URL, json=payload, timeout=HL_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"    [WARN] API error after {retries} retries: {e}")
                return None


def fetch_candles_range(coin: str, start_ms: int, end_ms: int, interval: str = "1h") -> list:
    """Загрузить свечи за диапазон с пагинацией (лимит 500 за запрос)."""
    interval_ms = {
        "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000,
    }
    step_ms = interval_ms.get(interval, 3_600_000) * 500

    all_candles = []
    cursor = start_ms

    while cursor < end_ms:
        chunk_end = min(cursor + step_ms, end_ms)
        data = _post({
            "type": "candleSnapshot",
            "req": {
                "coin": coin,
                "interval": interval,
                "startTime": cursor,
                "endTime": chunk_end,
            }
        })
        if not data or not isinstance(data, list):
            break

        for c in data:
            try:
                all_candles.append({
                    "time": c.get("t", 0),
                    "open":   float(c.get("o", "0")),
                    "high":   float(c.get("h", "0")),
                    "low":    float(c.get("l", "0")),
                    "close":  float(c.get("c", "0")),
                    "volume": float(c.get("v", "0")),
                })
            except (ValueError, TypeError):
                continue

        cursor = chunk_end
        if chunk_end < end_ms:
            time.sleep(0.3)  # rate limit

    # Дедупликация по времени
    seen = {}
    for c in all_candles:
        seen[c["time"]] = c
    result = sorted(seen.values(), key=lambda x: x["time"])
    return result


# ─── Resample свечей ──────────────────────────────────────────────────────────

def resample_candles(candles_1h: list, factor: int) -> list:
    """Сгруппировать 1h-свечи в factor-часовые."""
    if len(candles_1h) < factor:
        return []
    result = []
    for i in range(0, len(candles_1h) - factor + 1, factor):
        group = candles_1h[i:i + factor]
        result.append({
            "time":   group[0]["time"],
            "open":   group[0]["open"],
            "high":   max(c["high"] for c in group),
            "low":    min(c["low"] for c in group),
            "close":  group[-1]["close"],
            "volume": sum(c["volume"] for c in group),
        })
    return result


# ─── Бэктест ──────────────────────────────────────────────────────────────────

def run_backtest():
    print("=" * 60)
    print("   VASILY BACKTEST — 7 MONTHS 1H CANDLES")
    print("=" * 60)

    now_ms = int(time.time() * 1000)
    # 7 месяцев назад
    start_ms = now_ms - (210 * 24 * 3_600_000)
    start_dt = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
    end_dt   = datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc)

    print(f"Период: {start_dt.strftime('%d.%m.%Y')} — {end_dt.strftime('%d.%m.%Y')}")
    print(f"Монеты: {len(COINS)}")
    print(f"Фильтры: Time={TIME_FILTER_START_UTC:02d}-{TIME_FILTER_END_UTC:02d}UTC, Volume=avg×{VOLUME_FILTER_MULTIPLIER}")
    print()

    # ── 1. Загрузка данных ─────────────────────────────────────────────────
    coin_candles = {}
    for i, coin in enumerate(COINS):
        print(f"[{i+1}/{len(COINS)}] Загружаем {coin}...")
        candles = fetch_candles_range(coin, start_ms, now_ms, "1h")
        if not candles:
            print(f"  {coin}: нет данных, пропускаем")
            continue
        coin_candles[coin] = candles
        print(f"  {coin}: загружено {len(candles)} свечей")

    print()

    # ── 2. Симуляция ───────────────────────────────────────────────────────
    trades = []
    balance = INITIAL_BALANCE
    max_balance = INITIAL_BALANCE
    min_balance = INITIAL_BALANCE

    # Состояние: open_positions[coin] = {entry_price, direction, entry_idx, entry_time, size_usd}
    open_positions = {}
    # cooldown[coin] = last_close_idx
    cooldowns = {}

    # Используем BTC как "мастер-список" времён (все монеты должны иметь ~те же таймстемпы)
    master_coin = next(iter(coin_candles))
    master_candles = coin_candles[master_coin]
    total_steps = len(master_candles)

    print(f"Симуляция: {total_steps} шагов по каждой монете...")
    print()

    for step_idx in range(MIN_CANDLES_FOR_TA, total_steps):
        current_time_ms = master_candles[step_idx]["time"]

        for coin, candles in coin_candles.items():
            # Найти индекс, соответствующий текущему времени
            # (монеты могут иметь чуть разные длины)
            coin_idx = min(step_idx, len(candles) - 1)
            if coin_idx < MIN_CANDLES_FOR_TA:
                continue

            current_candle = candles[coin_idx]

            # ── Проверить открытую позицию ──────────────────────────────
            if coin in open_positions:
                pos = open_positions[coin]
                entry = pos["entry_price"]
                direction = pos["direction"]
                size_usd = pos["size_usd"]
                entry_idx = pos["entry_idx"]

                h = current_candle["high"]
                l = current_candle["low"]
                c = current_candle["close"]
                hold_hours = coin_idx - entry_idx

                sl_price = pos["sl"]
                tp_price = pos["tp"]

                exit_price = None
                exit_reason = None

                if direction == "LONG":
                    if l <= sl_price:
                        exit_price = sl_price
                        exit_reason = "SL"
                    elif h >= tp_price:
                        exit_price = tp_price
                        exit_reason = "TP"
                elif direction == "SHORT":
                    if h >= sl_price:
                        exit_price = sl_price
                        exit_reason = "SL"
                    elif l <= tp_price:
                        exit_price = tp_price
                        exit_reason = "TP"

                if exit_price is None and hold_hours >= MAX_HOLD_HOURS:
                    exit_price = c
                    exit_reason = "TIMEOUT"

                if exit_price is not None:
                    # Рассчитать P&L
                    dir_mult = 1 if direction == "LONG" else -1
                    pnl = ((exit_price - entry) / entry) * size_usd * LEVERAGE * dir_mult

                    balance += pnl
                    max_balance = max(max_balance, balance)
                    min_balance = min(min_balance, balance)

                    entry_dt = datetime.fromtimestamp(candles[entry_idx]["time"] / 1000, tz=timezone.utc)
                    exit_dt  = datetime.fromtimestamp(current_time_ms / 1000, tz=timezone.utc)

                    trades.append({
                        "coin": coin,
                        "direction": direction,
                        "entry_price": entry,
                        "exit_price": exit_price,
                        "entry_date": entry_dt.strftime("%d.%m.%Y %H:%M"),
                        "exit_date":  exit_dt.strftime("%d.%m.%Y %H:%M"),
                        "hold_hours": hold_hours,
                        "pnl": round(pnl, 4),
                        "exit_reason": exit_reason,
                        "balance_after": round(balance, 4),
                    })

                    del open_positions[coin]
                    cooldowns[coin] = coin_idx
                continue  # позиция открыта или только что закрыта

            # ── Cooldown check ───────────────────────────────────────────
            if coin in cooldowns and (coin_idx - cooldowns[coin]) < COOLDOWN_HOURS:
                continue

            # ── Временной фильтр: не торговать 02:00–06:00 UTC ─────────
            if TIME_FILTER_ENABLED:
                candle_dt = datetime.fromtimestamp(current_candle["time"] / 1000, tz=timezone.utc)
                hour_utc = candle_dt.hour
                if TIME_FILTER_START_UTC <= hour_utc < TIME_FILTER_END_UTC:
                    continue

            # ── Фильтр объёма: текущий объём > avg(20) × 1.5 ─────────
            if VOLUME_FILTER_ENABLED:
                lookback_start = max(0, coin_idx - VOLUME_LOOKBACK)
                vol_window = candles[lookback_start:coin_idx]
                if vol_window:
                    volumes = [c["volume"] for c in vol_window if c.get("volume", 0) > 0]
                    if volumes:
                        avg_vol = sum(volumes) / len(volumes)
                        current_vol = current_candle.get("volume", 0)
                        if avg_vol > 0 and current_vol < avg_vol * VOLUME_FILTER_MULTIPLIER:
                            continue
                    # Если volumes пустой — объём недоступен, пропускаем условие

            # ── Рассчитать TA на 1h ──────────────────────────────────────
            window_1h = candles[max(0, coin_idx - MIN_CANDLES_FOR_TA):coin_idx + 1]
            ta_1h = full_analysis(window_1h)
            if not ta_1h:
                continue

            # ── Resample для 4h и 1d ─────────────────────────────────────
            window_4h = resample_candles(window_1h, 4)
            window_1d = resample_candles(window_1h, 24)

            ta_4h = full_analysis(window_4h) if len(window_4h) >= 30 else None
            ta_1d = full_analysis(window_1d) if len(window_1d) >= 14 else None

            # ── MTF Confluence ───────────────────────────────────────────
            mtf = analyze_multi_timeframe(ta_1h, ta_4h, ta_1d)
            direction = mtf.get("direction", "NEUTRAL")
            weighted_score = mtf.get("weighted_score", 0)

            # Используем abs(weighted_score) как net_score
            net_score = abs(weighted_score)
            if direction == "NEUTRAL" or net_score < NET_SCORE_THRESHOLD:
                continue

            # ── Открыть позицию ──────────────────────────────────────────
            entry_price = current_candle["close"]
            if entry_price <= 0:
                continue

            # Динамический размер позиции: net_score ≥ 70 → 20%, иначе 10%
            if net_score >= NET_SCORE_HIGH:
                size_pct = POSITION_SIZE_HIGH_PCT
            else:
                size_pct = POSITION_SIZE_PCT
            size_usd = balance * size_pct

            # Фиксированный % SL/TP
            sl_dist = entry_price * SL_PCT
            tp_dist = entry_price * TP_PCT

            if direction == "LONG":
                sl = entry_price - sl_dist
                tp = entry_price + tp_dist
            else:  # SHORT
                sl = entry_price + sl_dist
                tp = entry_price - tp_dist

            open_positions[coin] = {
                "entry_price": entry_price,
                "direction": direction,
                "entry_idx": coin_idx,
                "size_usd": size_usd,
                "sl": sl,
                "tp": tp,
            }

    # Закрыть все оставшиеся позиции по последней свече
    for coin, pos in open_positions.items():
        candles = coin_candles[coin]
        last_candle = candles[-1]
        entry = pos["entry_price"]
        direction = pos["direction"]
        size_usd = pos["size_usd"]
        exit_price = last_candle["close"]
        dir_mult = 1 if direction == "LONG" else -1
        pnl = ((exit_price - entry) / entry) * size_usd * LEVERAGE * dir_mult
        balance += pnl
        max_balance = max(max_balance, balance)

        entry_dt = datetime.fromtimestamp(candles[pos["entry_idx"]]["time"] / 1000, tz=timezone.utc)
        exit_dt  = datetime.fromtimestamp(last_candle["time"] / 1000, tz=timezone.utc)

        trades.append({
            "coin": coin,
            "direction": direction,
            "entry_price": entry,
            "exit_price": exit_price,
            "entry_date": entry_dt.strftime("%d.%m.%Y %H:%M"),
            "exit_date":  exit_dt.strftime("%d.%m.%Y %H:%M"),
            "hold_hours": len(candles) - 1 - pos["entry_idx"],
            "pnl": round(pnl, 4),
            "exit_reason": "END_OF_DATA",
            "balance_after": round(balance, 4),
        })

    # ── 3. Статистика ──────────────────────────────────────────────────────
    total_trades = len(trades)
    winning = [t for t in trades if t["pnl"] > 0]
    losing  = [t for t in trades if t["pnl"] <= 0]

    win_rate = len(winning) / total_trades * 100 if total_trades > 0 else 0
    total_pnl = balance - INITIAL_BALANCE
    total_pnl_pct = (total_pnl / INITIAL_BALANCE) * 100

    max_drawdown_pct = ((max_balance - min_balance) / max_balance * 100) if max_balance > 0 else 0

    avg_win = sum(t["pnl"] for t in winning) / len(winning) if winning else 0
    avg_loss = sum(t["pnl"] for t in losing) / len(losing) if losing else 0

    gross_profit = sum(t["pnl"] for t in winning)
    gross_loss   = abs(sum(t["pnl"] for t in losing))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

    # По монетам
    coin_stats = {}
    for t in trades:
        coin = t["coin"]
        if coin not in coin_stats:
            coin_stats[coin] = {"trades": 0, "wins": 0, "pnl": 0.0}
        coin_stats[coin]["trades"] += 1
        coin_stats[coin]["pnl"] += t["pnl"]
        if t["pnl"] > 0:
            coin_stats[coin]["wins"] += 1

    # Лучшая и худшая сделки
    best_trade  = max(trades, key=lambda x: x["pnl"]) if trades else None
    worst_trade = min(trades, key=lambda x: x["pnl"]) if trades else None

    # ── 4. Вывод результатов ───────────────────────────────────────────────
    print()
    print("=== BACKTEST RESULTS ===")
    print(f"Период: {start_dt.strftime('%d.%m.%Y')} - {end_dt.strftime('%d.%m.%Y')}")
    print(f"Монеты: {len(COINS)}")
    print()
    print("Статистика:")
    print(f"  Всего сделок: {total_trades}")
    print(f"  Прибыльных:   {len(winning)} (Win Rate: {win_rate:.1f}%)")
    print(f"  Убыточных:    {len(losing)}")
    print(f"  Profit Factor: {profit_factor:.2f}")
    print()
    print(f"P&L (${INITIAL_BALANCE:.0f} баланс, {int(POSITION_SIZE_PCT*100)}% позиции, {LEVERAGE}x плечо):")
    sign = "+" if total_pnl >= 0 else ""
    print(f"  Общий P&L:     {sign}${total_pnl:.2f} ({sign}{total_pnl_pct:.1f}%)")
    print(f"  Макс просадка: {max_drawdown_pct:.1f}%")
    print(f"  Средняя прибыль: +${avg_win:.2f}")
    print(f"  Средний убыток:  ${avg_loss:.2f}")
    print()
    print("По монетам (топ):")
    sorted_coins = sorted(coin_stats.items(), key=lambda x: -abs(x[1]["pnl"]))
    for coin, cs in sorted_coins[:10]:
        wr = cs["wins"] / cs["trades"] * 100 if cs["trades"] > 0 else 0
        pnl_sign = "+" if cs["pnl"] >= 0 else ""
        print(f"  {coin}: {cs['trades']} сделок, Win Rate {wr:.0f}%, P&L {pnl_sign}${cs['pnl']:.2f}")

    print()
    if best_trade:
        print(f"Лучшая сделка: {best_trade['coin']} {best_trade['direction']} {best_trade['entry_date'][:10]} -> +${best_trade['pnl']:.2f}")
    if worst_trade:
        print(f"Худшая сделка: {worst_trade['coin']} {worst_trade['direction']} {worst_trade['entry_date'][:10]} -> ${worst_trade['pnl']:.2f}")

    # ── 5. Сохранить результаты ────────────────────────────────────────────
    data_dir = Path("/Users/vladimirprihodko/Папка тест/fixcraftvp/trading-bot/data")
    data_dir.mkdir(parents=True, exist_ok=True)

    results_data = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "period_start": start_dt.isoformat(),
        "period_end":   end_dt.isoformat(),
        "config": {
            "coins": COINS,
            "initial_balance": INITIAL_BALANCE,
            "position_size_pct": POSITION_SIZE_PCT,
            "leverage": LEVERAGE,
            "sl_pct": SL_PCT,
            "tp_pct": TP_PCT,
            "max_hold_hours": MAX_HOLD_HOURS,
            "cooldown_hours": COOLDOWN_HOURS,
            "net_score_threshold": NET_SCORE_THRESHOLD,
            "time_filter": f"{TIME_FILTER_START_UTC:02d}:00-{TIME_FILTER_END_UTC:02d}:00 UTC" if TIME_FILTER_ENABLED else "disabled",
            "volume_filter": f"vol > avg({VOLUME_LOOKBACK}) × {VOLUME_FILTER_MULTIPLIER}" if VOLUME_FILTER_ENABLED else "disabled",
        },
        "summary": {
            "total_trades": total_trades,
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 4) if profit_factor != float("inf") else None,
            "total_pnl": round(total_pnl, 4),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "final_balance": round(balance, 4),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "avg_win": round(avg_win, 4),
            "avg_loss": round(avg_loss, 4),
        },
        "coin_stats": {
            coin: {
                "trades": cs["trades"],
                "wins": cs["wins"],
                "win_rate": round(cs["wins"] / cs["trades"] * 100, 1) if cs["trades"] > 0 else 0,
                "pnl": round(cs["pnl"], 4),
            }
            for coin, cs in coin_stats.items()
        },
        "best_trade":  best_trade,
        "worst_trade": worst_trade,
        "trades": trades,
    }

    out_path = data_dir / "backtest_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results_data, f, ensure_ascii=False, indent=2)

    print()
    print(f"Детали сохранены: {out_path}")
    print("=" * 60)


if __name__ == "__main__":
    run_backtest()
