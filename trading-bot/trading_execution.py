#!/usr/bin/env python3
"""
Trading Execution Module — Василий.
Поддерживает: real mode (Hyperliquid), testnet, paper mode (fallback).
Использует hyperliquid-python-sdk для подписи и отправки ордеров.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Optional

import requests

log = logging.getLogger("vasily_exec")

# ── Logging setup ─────────────────────────────────────────────────────────
LOG_DIR = Path.home() / "logs"
LOG_DIR.mkdir(exist_ok=True)
_trade_log_path = LOG_DIR / "vasily-trades.log"
_trade_handler = logging.FileHandler(_trade_log_path, encoding="utf-8")
_trade_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
log.addHandler(_trade_handler)
log.setLevel(logging.INFO)

# ── Constants ─────────────────────────────────────────────────────────────
HL_EXCHANGE_URL = "https://api.hyperliquid.xyz/exchange"
HL_INFO_URL = "https://api.hyperliquid.xyz/info"
HL_TESTNET_EXCHANGE_URL = "https://api.hyperliquid-testnet.xyz/exchange"
HL_TESTNET_INFO_URL = "https://api.hyperliquid-testnet.xyz/info"

PAPER_PORTFOLIO_PATH = Path(__file__).resolve().parent / "data" / "paper_portfolio.json"


# ══════════════════════════════════════════════════════════════════════════
# Risk Manager
# ══════════════════════════════════════════════════════════════════════════
class RiskManager:
    """Контроль рисков перед каждым ордером."""

    def __init__(
        self,
        daily_loss_limit_pct: float = 2.0,
        max_position_size_pct: float = 10.0,
        max_open_positions: int = 3,
        max_trades_per_day: int = 3,
        emergency_stop_pct: float = 50.0,
    ):
        self.daily_loss_limit_pct = daily_loss_limit_pct
        self.max_position_size_pct = max_position_size_pct
        self.max_open_positions = max_open_positions
        self.max_trades_per_day = max_trades_per_day
        self.emergency_stop_pct = emergency_stop_pct

        # State
        self._start_of_day_balance: float = 0.0
        self._current_day: date | None = None
        self._daily_realized_pnl: float = 0.0
        self._daily_trades_opened: int = 0
        self._emergency_triggered: bool = False

    def reset_day(self, balance: float) -> None:
        today = date.today()
        if self._current_day != today:
            self._current_day = today
            self._start_of_day_balance = balance
            self._daily_realized_pnl = 0.0
            self._daily_trades_opened = 0
            self._emergency_triggered = False
            log.info("RiskManager day reset: balance=%.2f", balance)

    def record_pnl(self, pnl: float) -> None:
        self._daily_realized_pnl += pnl

    def track_trade_opened(self) -> None:
        """Отслеживать открытие новой сделки в текущий день."""
        self._daily_trades_opened += 1

    def check_order(
        self,
        size_usd: float,
        balance: float,
        open_positions: int,
    ) -> tuple[bool, str]:
        """Проверяет ордер. Возвращает (ok, reason)."""
        self.reset_day(balance)

        if self._emergency_triggered:
            return False, "EMERGENCY STOP активен. Торговля остановлена до конца дня."

        # Emergency stop
        if self._start_of_day_balance > 0:
            day_loss_pct = abs(min(0, self._daily_realized_pnl)) / self._start_of_day_balance * 100
            if day_loss_pct >= self.emergency_stop_pct:
                self._emergency_triggered = True
                log.critical("EMERGENCY STOP: дневной убыток %.1f%% >= %.1f%%", day_loss_pct, self.emergency_stop_pct)
                return False, f"EMERGENCY STOP: убыток за день {day_loss_pct:.1f}% (лимит {self.emergency_stop_pct}%)"

        # Daily loss limit
        if self._start_of_day_balance > 0:
            daily_limit_usd = self._start_of_day_balance * self.daily_loss_limit_pct / 100
            if abs(min(0, self._daily_realized_pnl)) >= daily_limit_usd:
                return False, f"Дневной лимит убытков исчерпан ({self.daily_loss_limit_pct}% = ${daily_limit_usd:.2f})"

        # Max position size
        if balance > 0:
            max_size = balance * self.max_position_size_pct / 100
            if size_usd > max_size:
                return False, f"Размер ${size_usd:.0f} > макс {self.max_position_size_pct}% баланса (${max_size:.0f})"

        # Max open positions
        if open_positions >= self.max_open_positions:
            return False, f"Уже {open_positions} открытых позиций (макс {self.max_open_positions})"

        # Max trades per day
        if self._daily_trades_opened >= self.max_trades_per_day:
            return False, f"Уже открыто {self._daily_trades_opened} сделок сегодня (макс {self.max_trades_per_day})"

        return True, "OK"


# ══════════════════════════════════════════════════════════════════════════
# Paper Trading Engine (fallback без ключей)
# ══════════════════════════════════════════════════════════════════════════
class PaperTrader:
    """Бумажная торговля — имитация для тестов."""

    def __init__(self, initial_balance: float = 1000.0):
        self._data = self._load()
        if not self._data.get("balance"):
            self._data = {
                "balance": initial_balance,
                "positions": [],
                "history": [],
                "created": datetime.now(timezone.utc).isoformat(),
            }
            self._save()

    def _load(self) -> dict:
        if PAPER_PORTFOLIO_PATH.exists():
            try:
                return json.loads(PAPER_PORTFOLIO_PATH.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save(self) -> None:
        PAPER_PORTFOLIO_PATH.parent.mkdir(parents=True, exist_ok=True)
        PAPER_PORTFOLIO_PATH.write_text(json.dumps(self._data, indent=2, default=str))

    def _get_price(self, coin: str) -> float:
        """Текущая mid-цена с Hyperliquid."""
        try:
            resp = requests.post(HL_INFO_URL, json={"type": "allMids"}, timeout=10)
            mids = resp.json()
            return float(mids.get(coin, 0))
        except Exception:
            return 0.0

    def get_balance(self) -> float:
        return self._data.get("balance", 0.0)

    def get_positions(self) -> list[dict]:
        return self._data.get("positions", [])

    def place_order(
        self,
        coin: str,
        side: str,
        size_usd: float,
        leverage: float = 5,
        sl_pct: float = 2.0,
        tp_pct: float = 4.0,
    ) -> dict:
        price = self._get_price(coin)
        if price <= 0:
            return {"ok": False, "error": f"Не удалось получить цену {coin}"}

        coin_qty = size_usd / price
        sl_price = price * (1 - sl_pct / 100) if side == "BUY" else price * (1 + sl_pct / 100)
        tp_price = price * (1 + tp_pct / 100) if side == "BUY" else price * (1 - tp_pct / 100)

        position = {
            "coin": coin,
            "side": side,
            "size_usd": round(size_usd, 2),
            "size_coin": round(coin_qty, 6),
            "entry_price": round(price, 6),
            "leverage": leverage,
            "stop_loss": round(sl_price, 6),
            "take_profit": round(tp_price, 6),
            "opened_at": datetime.now(timezone.utc).isoformat(),
        }
        self._data.setdefault("positions", []).append(position)
        self._save()
        log.info("PAPER ORDER: %s %s $%.2f @ %.4f (SL=%.4f TP=%.4f)", side, coin, size_usd, price, sl_price, tp_price)
        return {"ok": True, "mode": "paper", "position": position}

    def close_position(self, coin: str) -> dict:
        positions = self._data.get("positions", [])
        to_close = [p for p in positions if p["coin"] == coin]
        if not to_close:
            return {"ok": False, "error": f"Нет открытой позиции {coin}"}

        price = self._get_price(coin)
        if price <= 0:
            return {"ok": False, "error": f"Не удалось получить цену {coin}"}

        results = []
        for pos in to_close:
            entry = pos["entry_price"]
            side = pos["side"]
            qty = pos["size_coin"]
            if side == "BUY":
                pnl = (price - entry) * qty
            else:
                pnl = (entry - price) * qty

            self._data["balance"] = self._data.get("balance", 0) + pnl
            self._data.setdefault("history", []).append({
                **pos,
                "close_price": round(price, 6),
                "pnl": round(pnl, 4),
                "closed_at": datetime.now(timezone.utc).isoformat(),
            })
            results.append({"coin": coin, "pnl": round(pnl, 4), "close_price": price})

        self._data["positions"] = [p for p in positions if p["coin"] != coin]
        self._save()
        total_pnl = sum(r["pnl"] for r in results)
        log.info("PAPER CLOSE: %s @ %.4f | PnL: %.4f", coin, price, total_pnl)
        self.save_daily_snapshot()
        return {"ok": True, "mode": "paper", "closed": results, "total_pnl": total_pnl}

    def save_daily_snapshot(self) -> None:
        """Сохраняет ежедневный snapshot баланса и P&L в daily_pnl.json."""
        pnl_path = Path(__file__).resolve().parent / "data" / "daily_pnl.json"
        pnl_path.parent.mkdir(parents=True, exist_ok=True)

        snapshots: list[dict] = []
        if pnl_path.exists():
            try:
                snapshots = json.loads(pnl_path.read_text())
            except (json.JSONDecodeError, OSError):
                snapshots = []

        today_str = date.today().isoformat()
        balance = self.get_balance()
        history = self._data.get("history", [])

        # Считаем сделки и P&L за сегодня
        today_trades = [t for t in history if t.get("closed_at", "")[:10] == today_str]
        pnl_day = sum(t.get("pnl", 0) for t in today_trades)
        pnl_pct = (pnl_day / (balance - pnl_day) * 100) if (balance - pnl_day) > 0 else 0.0

        entry = {
            "date": today_str,
            "balance": round(balance, 2),
            "pnl_day": round(pnl_day, 4),
            "pnl_pct": round(pnl_pct, 2),
            "trades": len(today_trades),
        }

        # Обновляем запись за сегодня или добавляем новую
        updated = False
        for i, s in enumerate(snapshots):
            if s.get("date") == today_str:
                snapshots[i] = entry
                updated = True
                break
        if not updated:
            snapshots.append(entry)

        pnl_path.write_text(json.dumps(snapshots, indent=2, default=str))
        log.info("Daily snapshot saved: %s", entry)


# ══════════════════════════════════════════════════════════════════════════
# Real Trading Engine (Hyperliquid SDK)
# ══════════════════════════════════════════════════════════════════════════
class HyperliquidTrader:
    """Торговля через hyperliquid-python-sdk."""

    def __init__(self, private_key: str, testnet: bool = False):
        self._testnet = testnet
        self._info_url = HL_TESTNET_INFO_URL if testnet else HL_INFO_URL
        self._exchange_url = HL_TESTNET_EXCHANGE_URL if testnet else HL_EXCHANGE_URL

        try:
            from hyperliquid.info import Info
            from hyperliquid.exchange import Exchange
            from hyperliquid.utils import constants

            base_url = constants.TESTNET_API_URL if testnet else constants.MAINNET_API_URL
            self._info = Info(base_url, skip_ws=True)
            self._exchange = Exchange(
                wallet=None,  # SDK принимает private_key отдельно
                base_url=base_url,
            )
            # SDK хранит ключ внутри exchange
            self._exchange.wallet = self._init_wallet(private_key)
            self._address = self._exchange.wallet.address
            self._sdk_available = True
            log.info("HyperliquidTrader init: sdk=OK testnet=%s addr=%s", testnet, self._address)
        except ImportError:
            log.warning("hyperliquid-python-sdk не установлен, fallback на REST API")
            self._sdk_available = False
            self._private_key = private_key
            self._address = None
            self._info = None
            self._exchange = None

    @staticmethod
    def _init_wallet(private_key: str):
        """Создаёт eth_account wallet из private key."""
        try:
            from eth_account import Account
            return Account.from_key(private_key)
        except ImportError:
            log.error("eth_account не установлен")
            return None

    def get_balance(self) -> float:
        """Возвращает equity (баланс + нереализованный PnL)."""
        try:
            if self._sdk_available and self._info:
                state = self._info.user_state(self._address)
            else:
                resp = requests.post(
                    self._info_url,
                    json={"type": "clearinghouseState", "user": self._address},
                    timeout=15,
                )
                state = resp.json()

            margin = state.get("marginSummary", {})
            return float(margin.get("accountValue", 0))
        except Exception as e:
            log.error("get_balance error: %s", e)
            return 0.0

    def get_positions(self) -> list[dict]:
        """Текущие позиции."""
        try:
            if self._sdk_available and self._info:
                state = self._info.user_state(self._address)
            else:
                resp = requests.post(
                    self._info_url,
                    json={"type": "clearinghouseState", "user": self._address},
                    timeout=15,
                )
                state = resp.json()

            positions = []
            for ap in state.get("assetPositions", []):
                p = ap.get("position", {})
                szi = float(p.get("szi", "0"))
                if abs(szi) < 1e-8:
                    continue
                entry = float(p.get("entryPx", "0"))
                positions.append({
                    "coin": p.get("coin", ""),
                    "side": "LONG" if szi > 0 else "SHORT",
                    "size_coin": abs(szi),
                    "size_usd": abs(szi) * entry,
                    "entry_price": entry,
                    "unrealized_pnl": float(p.get("unrealizedPnl", "0")),
                    "leverage": float(p.get("leverage", {}).get("value", "1")) if isinstance(p.get("leverage"), dict) else 1,
                })
            return positions
        except Exception as e:
            log.error("get_positions error: %s", e)
            return []

    def _get_mid_price(self, coin: str) -> float:
        try:
            resp = requests.post(HL_INFO_URL, json={"type": "allMids"}, timeout=10)
            mids = resp.json()
            return float(mids.get(coin, 0))
        except Exception:
            return 0.0

    def _get_sz_decimals(self, coin: str) -> int:
        """Get size decimals for rounding from Hyperliquid meta."""
        try:
            resp = requests.post(self._info_url, json={"type": "meta"}, timeout=10)
            meta = resp.json()
            for asset in meta.get("universe", []):
                if asset.get("name") == coin:
                    return int(asset.get("szDecimals", 2))
        except Exception:
            pass
        return 2

    def place_order(
        self,
        coin: str,
        side: str,
        size_usd: float,
        leverage: float = 5,
        sl_pct: float = 2.0,
        tp_pct: float = 4.0,
    ) -> dict:
        """Размещает market order + SL/TP ордера."""
        price = self._get_mid_price(coin)
        if price <= 0:
            return {"ok": False, "error": f"Не удалось получить цену {coin}"}

        sz_decimals = self._get_sz_decimals(coin)
        coin_qty = round(size_usd / price, sz_decimals)
        is_buy = side.upper() == "BUY"

        # SL/TP prices
        if is_buy:
            sl_price = round(price * (1 - sl_pct / 100), 2)
            tp_price = round(price * (1 + tp_pct / 100), 2)
        else:
            sl_price = round(price * (1 + sl_pct / 100), 2)
            tp_price = round(price * (1 - tp_pct / 100), 2)

        try:
            if self._sdk_available and self._exchange:
                # Set leverage first
                self._exchange.update_leverage(leverage, coin)

                # Market order
                result = self._exchange.market_open(
                    coin=coin,
                    is_buy=is_buy,
                    sz=coin_qty,
                    slippage=0.01,  # 1% slippage
                )

                log.info("REAL ORDER: %s %s %.6f @ ~%.4f | result=%s", side, coin, coin_qty, price, result)

                # Place SL
                self._exchange.order(
                    coin=coin,
                    is_buy=not is_buy,
                    sz=coin_qty,
                    limit_px=sl_price,
                    order_type={"trigger": {"triggerPx": sl_price, "isMarket": True, "tpsl": "sl"}},
                )

                # Place TP
                self._exchange.order(
                    coin=coin,
                    is_buy=not is_buy,
                    sz=coin_qty,
                    limit_px=tp_price,
                    order_type={"trigger": {"triggerPx": tp_price, "isMarket": True, "tpsl": "tp"}},
                )

                return {
                    "ok": True,
                    "mode": "testnet" if self._testnet else "mainnet",
                    "coin": coin,
                    "side": side,
                    "size_usd": size_usd,
                    "size_coin": coin_qty,
                    "entry_price": price,
                    "stop_loss": sl_price,
                    "take_profit": tp_price,
                    "leverage": leverage,
                    "result": str(result),
                }
            else:
                return {"ok": False, "error": "SDK не доступен, установите hyperliquid-python-sdk"}

        except Exception as e:
            log.error("place_order error: %s", e)
            return {"ok": False, "error": str(e)}

    def close_position(self, coin: str) -> dict:
        """Закрывает все позиции по монете."""
        positions = self.get_positions()
        to_close = [p for p in positions if p["coin"] == coin]
        if not to_close:
            return {"ok": False, "error": f"Нет открытой позиции {coin}"}

        try:
            if self._sdk_available and self._exchange:
                results = []
                for pos in to_close:
                    is_buy = pos["side"] == "SHORT"  # Закрытие = обратная сторона
                    result = self._exchange.market_close(coin=coin)
                    results.append(str(result))
                    log.info("REAL CLOSE: %s | result=%s", coin, result)

                return {
                    "ok": True,
                    "mode": "testnet" if self._testnet else "mainnet",
                    "coin": coin,
                    "results": results,
                }
            else:
                return {"ok": False, "error": "SDK не доступен"}
        except Exception as e:
            log.error("close_position error: %s", e)
            return {"ok": False, "error": str(e)}


# ══════════════════════════════════════════════════════════════════════════
# Main Executor (facade)
# ══════════════════════════════════════════════════════════════════════════
class TradingExecutor:
    """
    Единый интерфейс для торговли.
    Автоматически выбирает режим:
      - paper: если HL_PRIVATE_KEY не задан
      - testnet: если HL_TESTNET=true
      - mainnet: если HL_PRIVATE_KEY задан и HL_TESTNET != true
    """

    def __init__(self):
        self._private_key = os.environ.get("HL_PRIVATE_KEY", "")
        self._testnet = os.environ.get("HL_TESTNET", "").lower() in ("true", "1", "yes")
        self.risk = RiskManager()

        if self._private_key:
            self._trader = HyperliquidTrader(self._private_key, testnet=self._testnet)
            self._mode = "testnet" if self._testnet else "mainnet"
        else:
            self._trader = PaperTrader(initial_balance=1000.0)
            self._mode = "paper"

        log.info("TradingExecutor init: mode=%s", self._mode)

    @property
    def mode(self) -> str:
        return self._mode

    def get_balance(self) -> float:
        return self._trader.get_balance()

    def get_positions(self) -> list[dict]:
        return self._trader.get_positions()

    def place_order(
        self,
        coin: str,
        side: str,
        size_usd: float,
        leverage: float = 5,
        sl_pct: float = 2.0,
        tp_pct: float = 4.0,
    ) -> dict:
        """Ордер через risk manager → trader."""
        balance = self.get_balance()
        positions = self.get_positions()

        # Risk check
        ok, reason = self.risk.check_order(size_usd, balance, len(positions))
        if not ok:
            log.warning("RISK BLOCKED: %s %s $%.2f — %s", side, coin, size_usd, reason)
            return {"ok": False, "error": f"Risk Manager: {reason}"}

        result = self._trader.place_order(
            coin=coin,
            side=side.upper(),
            size_usd=size_usd,
            leverage=leverage,
            sl_pct=sl_pct,
            tp_pct=tp_pct,
        )

        # Record PnL if closing resulted in PnL (paper)
        if result.get("ok") and result.get("total_pnl"):
            self.risk.record_pnl(result["total_pnl"])

        # Track new trade
        if result.get("ok"):
            self.risk.track_trade_opened()

        return result

    def close_position(self, coin: str) -> dict:
        result = self._trader.close_position(coin)
        if result.get("ok") and result.get("total_pnl"):
            self.risk.record_pnl(result["total_pnl"])
        return result

    def get_status(self) -> dict:
        """Статус для Telegram."""
        balance = self.get_balance()
        positions = self.get_positions()
        return {
            "mode": self._mode,
            "balance": balance,
            "open_positions": len(positions),
            "positions": positions,
            "risk": {
                "daily_loss_limit": f"{self.risk.daily_loss_limit_pct}%",
                "max_position_size": f"{self.risk.max_position_size_pct}%",
                "max_positions": self.risk.max_open_positions,
                "emergency_stop": f"{self.risk.emergency_stop_pct}%",
                "daily_pnl": round(self.risk._daily_realized_pnl, 2),
                "emergency_triggered": self.risk._emergency_triggered,
            },
        }

    def __repr__(self) -> str:
        return f"<TradingExecutor mode={self._mode}>"


# ── Module-level convenience functions ────────────────────────────────────
_executor: TradingExecutor | None = None


def get_executor() -> TradingExecutor:
    """Singleton."""
    global _executor
    if _executor is None:
        _executor = TradingExecutor()
    return _executor


def place_order(coin: str, side: str, size_usd: float, **kw) -> dict:
    return get_executor().place_order(coin, side, size_usd, **kw)


def close_position(coin: str) -> dict:
    return get_executor().close_position(coin)


def get_positions() -> list[dict]:
    return get_executor().get_positions()


def get_balance() -> float:
    return get_executor().get_balance()


if __name__ == "__main__":
    executor = TradingExecutor()
    print(f"Mode: {executor.mode}")
    print(f"Balance: {executor.get_balance()}")
    print(f"Positions: {executor.get_positions()}")
    print(f"Status: {executor.get_status()}")
