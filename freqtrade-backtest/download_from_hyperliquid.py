#!/usr/bin/env python3
"""
Скачивает OHLCV данные с Hyperliquid и сохраняет в формат Freqtrade JSON.
"""
import json
import time
import requests
from datetime import datetime, timezone
from pathlib import Path

HL_INFO_URL = "https://api.hyperliquid.xyz/info"
COINS = ["ETH", "XRP", "AVAX", "BTC"]
TIMEFRAMES = {
    "1h": 3_600_000,
    "4h": 14_400_000,
}
DAYS = 210  # 7 месяцев

# Freqtrade data dir
DATA_DIR = Path(__file__).parent / "user_data" / "data" / "hyperliquid"


def fetch_candles(coin: str, interval: str, start_ms: int, end_ms: int) -> list:
    """Загрузить свечи с пагинацией."""
    step_ms = TIMEFRAMES[interval] * 500
    all_candles = []
    cursor = start_ms
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    while cursor < end_ms:
        chunk_end = min(cursor + step_ms, end_ms)
        try:
            resp = session.post(HL_INFO_URL, json={
                "type": "candleSnapshot",
                "req": {
                    "coin": coin,
                    "interval": interval,
                    "startTime": cursor,
                    "endTime": chunk_end,
                }
            }, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  Error: {e}")
            break

        if not data or not isinstance(data, list):
            break

        for c in data:
            try:
                ts_ms = c.get("t", 0)
                all_candles.append([
                    ts_ms,                        # timestamp (ms)
                    float(c.get("o", "0")),       # open
                    float(c.get("h", "0")),       # high
                    float(c.get("l", "0")),       # low
                    float(c.get("c", "0")),       # close
                    float(c.get("v", "0")),       # volume
                ])
            except (ValueError, TypeError):
                continue

        cursor = chunk_end
        if chunk_end < end_ms:
            time.sleep(0.3)

    # Дедупликация
    seen = {}
    for c in all_candles:
        seen[c[0]] = c
    return sorted(seen.values(), key=lambda x: x[0])


def main():
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (DAYS * 24 * 3_600_000)

    start_dt = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
    end_dt = datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc)
    print(f"Период: {start_dt.strftime('%Y-%m-%d')} — {end_dt.strftime('%Y-%m-%d')}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    for coin in COINS:
        pair_name = f"{coin}_USDT"  # Freqtrade naming
        for tf in TIMEFRAMES:
            print(f"Скачиваю {coin} {tf}...")
            candles = fetch_candles(coin, tf, start_ms, now_ms)
            print(f"  Получено {len(candles)} свечей")

            if not candles:
                continue

            # Freqtrade JSON format: [[timestamp, open, high, low, close, volume], ...]
            filename = f"{pair_name}-{tf}.json"
            filepath = DATA_DIR / filename
            with open(filepath, "w") as f:
                json.dump(candles, f)
            print(f"  Сохранено: {filepath}")

    print("\nГотово!")


if __name__ == "__main__":
    main()
