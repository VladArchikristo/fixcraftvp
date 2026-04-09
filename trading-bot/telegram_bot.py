#!/usr/bin/env python3
"""
Василий — торговый советник Telegram бот.
Singleton, no while-loop (LaunchAgent restarts), heartbeat, Claude CLI.
"""
from __future__ import annotations

import atexit
import os
import sys
import fcntl
import signal
import time
import logging
from logging.handlers import RotatingFileHandler
import subprocess
import asyncio
from pathlib import Path
from datetime import datetime
from collections import deque
from concurrent.futures import ThreadPoolExecutor

import json
import tempfile
from dotenv import load_dotenv
from telegram import Update
from telegram.error import Conflict, NetworkError, TimedOut
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")

BOT_TOKEN = os.getenv("VASILY_BOT_TOKEN", "")
CHAT_ID = int(os.getenv("VASILY_CHAT_ID", "244710532"))
ALLOWED_USER = 244710532
CLAUDE_PATH = "/Users/vladimirprihodko/.local/bin/claude"
WORKING_DIR = "/Users/vladimirprihodko/Папка тест/fixcraftvp/"
CLAUDE_TIMEOUT = 3600  # 1 hour for complex tasks with tools
RATE_LIMIT_SEC = 5  # min seconds between messages
MAX_PROMPT_CHARS = 50000  # max total prompt size to Claude

LOG_DIR = Path.home() / "logs"
LOG_DIR.mkdir(exist_ok=True)
PID_FILE = LOG_DIR / "vasily-bot.pid"
HEARTBEAT_FILE = LOG_DIR / "vasily-heartbeat"
LOCK_FILE = LOG_DIR / "vasily-bot.lock"

PORTFOLIO_FILE = SCRIPT_DIR / "data" / "paper_portfolio.json"

BASE_SYSTEM_PROMPT = (
    "Ты Василий — профессиональный крипто-трейдер на Hyperliquid perpetual futures. "
    "Даёшь советы по криптовалютам и торговле. "
    "Говоришь уверенно, по делу, без воды. "
    "Используешь профессиональную терминологию но объясняешь понятно.\n\n"
    "ТВОЙ ИНСТРУМЕНТАРИЙ:\n"
    "- Реальные данные с Hyperliquid: цены, funding rates, open interest, order book\n"
    "- Полный тех.анализ: RSI-14, StochRSI, MACD(12,26,9), EMA 20/50/200, Bollinger Bands(20,2), ATR-14, ADX-14\n"
    "- Volume Profile, Support/Resistance уровни\n"
    "- Scoring система: -100 до +100 (сумма всех индикаторов)\n"
    "- Новости RSS (CoinDesk, Cointelegraph, Decrypt)\n"
    "- Fear & Greed Index, BTC Dominance\n"
    "- У тебя есть доступ к инструментам: Read, Edit, Write, Grep, Glob, Bash.\n\n"
    "КОМАНДЫ TELEGRAM:\n"
    "- /scan — полный скан рынка (Hyperliquid + TA + Claude анализ)\n"
    "- /ta — быстрый тех.анализ без Claude\n"
    "- /funding — funding rates и OI\n"
    "- /portfolio — портфель и P&L\n\n"
    "ПРАВИЛА УПРАВЛЕНИЯ РИСКАМИ:\n"
    "- При открытии КАЖДОЙ позиции ОБЯЗАТЕЛЬНО ставь stop_loss и take_profit.\n"
    "- SL ставится по ATR: 1.5-2x ATR от входа или ближайший уровень поддержки.\n"
    "- TP ставится по уровням сопротивления. Минимальный R:R = 1:2.\n"
    "- Trailing Stop автоматически подтягивается.\n"
    "- Дневной лимит убытков: $10 (10% от капитала).\n"
    "- Макс 2 позиции одного направления.\n"
    "- RSI > 75 = блок LONG, RSI < 25 = блок SHORT.\n"
    "- Формат в JSON позиции: \"stop_loss\": цена, \"take_profit\": цена.\n"
    "- Если видишь позицию без SL/TP — предупреди и предложи установить.\n\n"
    "СТРАТЕГИИ:\n"
    "- Trend Following: вход по тренду на откатах к EMA20/50. ADX > 25 = тренд силён.\n"
    "- Mean Reversion: покупка на oversold, продажа на overbought. ADX < 20 = боковик, OK для MR.\n"
    "- Breakout: прорыв уровня с объёмом\n"
    "- Funding Arb: SHORT при extreme positive funding, LONG при negative\n"
    "- ПРАВИЛО ADX: НИКОГДА не торгуй против тренда при ADX > 25! Если DI+ > DI- = тренд вверх, блок SHORT.\n\n"
    "== КОМАНДА НА MAC MINI ==\n"
    "Ты часть команды ботов Владимира. Умей делегировать коллегам:\n\n"
    "• Костя (@KostyaCoderBot) — программист-архитектор.\n"
    "  Делегируй: код, скрипты, баги, фичи в market_scan.py и боте.\n"
    "  echo 'задача' | bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-kostya.sh'\n\n"
    "• Мыслитель Филип — промт-инженер, полиглот.\n"
    "  Делегируй: создать структурированное ТЗ или промт для анализа рынка.\n"
    "  echo 'задача' | bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-philip.sh'\n\n"
    "• Маша (@masha_marketer_bot) — маркетолог.\n"
    "  Если пользователь спрашивает про маркетинг проекта — упомяни Машу.\n\n"
    "• Beast (@Antropic_BeastBot) — главный ассистент Владимира.\n\n"
    "НЕЛЬЗЯ ТРОГАТЬ: beast-bot/bot.py, .env файлы, launcher.sh скрипты.\n"
)

START_TIME = datetime.now()
_claude_executor = ThreadPoolExecutor(max_workers=1)
_processing = False  # True while Claude request is in flight
_processing_lock = asyncio.Lock()
_message_queue: deque = deque(maxlen=5)  # Message queue for sequential processing
_queue_task: asyncio.Task | None = None


def _get_claude_env() -> dict:
    """Clean env for Claude CLI — only essentials, no stale tokens."""
    home = Path.home()
    nvm_node_bin = ""
    nvm_dir = home / ".nvm" / "versions" / "node"
    if nvm_dir.exists():
        versions = sorted(nvm_dir.iterdir(), reverse=True)
        if versions:
            nvm_node_bin = str(versions[0] / "bin")
            # Ensure node is reachable via ~/.local/bin (no sudo needed)
            local_bin = home / ".local" / "bin"
            local_bin.mkdir(parents=True, exist_ok=True)
            local_node = local_bin / "node"
            nvm_node = Path(nvm_node_bin) / "node"
            if not local_node.exists() and nvm_node.exists():
                local_node.symlink_to(nvm_node)
    base_path = os.environ.get("PATH", "/usr/bin:/usr/local/bin")
    extra = f"{home}/.local/bin:{nvm_node_bin}:{home}/.bun/bin" if nvm_node_bin else f"{home}/.local/bin:{home}/.bun/bin"
    env = {
        "HOME": str(home),
        "PATH": f"{extra}:{base_path}",
        "USER": os.environ.get("USER", ""),
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        "TERM": os.environ.get("TERM", "xterm-256color"),
    }
    tmpdir = os.environ.get("TMPDIR")
    if tmpdir:
        env["TMPDIR"] = tmpdir
    return env

# ---------------------------------------------------------------------------
# Logging — stdout + rotating file (max 2MB x 3 backups)
# ---------------------------------------------------------------------------
class _SafeFormatter(logging.Formatter):
    """Formatter that redacts bot token from ALL log output."""
    def format(self, record):
        msg = super().format(record)
        if BOT_TOKEN:
            msg = msg.replace(BOT_TOKEN, "***")
        return msg


_log_formatter = _SafeFormatter("%(asctime)s [%(levelname)s] %(message)s")
_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.setFormatter(_log_formatter)

_file_handler = RotatingFileHandler(
    LOG_DIR / "vasily-bot-main.log", maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_file_handler.setFormatter(_log_formatter)

logging.basicConfig(level=logging.INFO, handlers=[_stdout_handler, _file_handler])
log = logging.getLogger("vasily")

# ---------------------------------------------------------------------------
# Singleton lock
# ---------------------------------------------------------------------------
_lock_fd = None


def acquire_lock():
    global _lock_fd
    _lock_fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        _lock_fd.close()
        _lock_fd = None
        log.info("Another instance is already running. Exiting.")
        sys.exit(0)
    _lock_fd.write(str(os.getpid()))
    _lock_fd.flush()


# ---------------------------------------------------------------------------
# PID & heartbeat
# ---------------------------------------------------------------------------
def write_pid():
    PID_FILE.write_text(str(os.getpid()))
    log.info("PID %d written to %s", os.getpid(), PID_FILE)


def write_heartbeat():
    HEARTBEAT_FILE.write_text(datetime.now().isoformat())


# ---------------------------------------------------------------------------
# Heartbeat job (runs every 60 s via application.job_queue)
# ---------------------------------------------------------------------------
async def heartbeat_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        write_heartbeat()
    except Exception as e:
        log.error("Heartbeat write failed: %s", e)


# ---------------------------------------------------------------------------
# User history (persistent, saved to disk)
# ---------------------------------------------------------------------------
HISTORY_FILE = SCRIPT_DIR / "history.json"
user_history: deque[dict] = deque(maxlen=30)


# Full conversation log (never truncated, appends forever)
CONVERSATION_LOG = SCRIPT_DIR / "conversation_log.jsonl"


def _log_conversation(role: str, text: str, user_id: int | None = None):
    """Append a single message to the permanent conversation log."""
    entry = {
        "ts": datetime.now().isoformat(),
        "role": role,
        "user_id": user_id,
        "text": text[:5000],
    }
    try:
        with open(CONVERSATION_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        log.warning("Failed to write conversation log: %s", e)


def _load_history():
    """Load history from disk on startup. Backs up corrupted files."""
    if not HISTORY_FILE.exists():
        return
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("history is not a list")
        for item in data[-30:]:
            if isinstance(item, dict) and "role" in item and "text" in item:
                user_history.append(item)
        log.info("Loaded %d history messages from disk", len(user_history))
    except (json.JSONDecodeError, ValueError) as e:
        log.error("History file corrupted: %s. Backing up and starting fresh.", e)
        try:
            HISTORY_FILE.rename(HISTORY_FILE.with_suffix(".json.bak"))
        except Exception:
            pass
    except Exception as e:
        log.warning("Failed to load history: %s", e)


def _save_history():
    """Save history to disk atomically (write to tmp, then rename)."""
    tmp_path = None
    try:
        data = json.dumps(list(user_history), ensure_ascii=False, indent=None)
        fd, tmp_path = tempfile.mkstemp(dir=SCRIPT_DIR, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp_path, str(HISTORY_FILE))
        tmp_path = None  # replaced successfully, no cleanup needed
    except Exception as e:
        log.warning("Failed to save history: %s", e)
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def history_prompt() -> str:
    if not user_history:
        return ""
    lines = []
    total_chars = 0
    for msg in reversed(list(user_history)):
        role = "Пользователь" if msg["role"] == "user" else "Василий"
        line = f"{role}: {msg['text'][:1000]}"
        total_chars += len(line)
        if total_chars > 15000:
            break
        lines.append(line)
    lines.reverse()
    return "\n".join(lines)


def _load_portfolio() -> dict:
    """Load paper portfolio from disk with shared file lock."""
    lock_path = PORTFOLIO_FILE.with_suffix(".json.lock")
    lock_fd = None
    try:
        lock_fd = open(lock_path, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_SH)  # Shared lock — safe concurrent reads
        data = json.loads(PORTFOLIO_FILE.read_text(encoding="utf-8"))
        # Normalize: "balance" → "cash" (backward compat)
        if "cash" not in data and "balance" in data:
            data["cash"] = data.pop("balance")
        data.setdefault("initial_capital", 100)
        data.setdefault("cash", 100)
        data.setdefault("positions", [])
        data.setdefault("closed_trades", [])
        data.setdefault("scan_history", [])
        return data
    except Exception:
        return {"initial_capital": 100, "cash": 100, "positions": [], "closed_trades": [], "scan_history": []}
    finally:
        if lock_fd:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                lock_fd.close()
            except Exception:
                pass


def _portfolio_summary() -> str:
    """Build a short portfolio summary for the system prompt."""
    p = _load_portfolio()
    lines = [f"Кэш: ${p['cash']:.2f}"]
    for pos in p.get("positions", []):
        entry = pos.get("entry", pos.get("entry_price", 0))
        sl = pos.get("stop_loss")
        tp = pos.get("take_profit")
        sl_tp = f" SL:${sl:.2f} TP:${tp:.2f}" if sl and tp else " [БЕЗ SL/TP!]"
        lines.append(f"  {pos.get('side','LONG')} {pos['asset']}: ${pos.get('size_usd',0):.0f} @ ${entry:.2f}{sl_tp}")
    if not p.get("positions"):
        lines.append("  Нет открытых позиций")
    closed = p.get("closed_trades", [])
    if closed:
        wins = sum(1 for t in closed if t.get("pnl_usd", 0) > 0)
        losses = len(closed) - wins
        lines.append(f"  Закрытых сделок: {len(closed)} (W:{wins} L:{losses})")
    return "\n".join(lines)


def _build_system_prompt() -> str:
    """System prompt with current portfolio context."""
    portfolio_ctx = _portfolio_summary()
    return (
        f"{BASE_SYSTEM_PROMPT}\n\n"
        f"ТЕКУЩИЙ ПОРТФЕЛЬ (paper trading):\n{portfolio_ctx}\n\n"
        f"Файл портфеля: {PORTFOLIO_FILE}\n"
        f"Если пользователь просит изменить портфель — обнови JSON через Edit."
    )


def _split_message(text: str, limit: int = 4096) -> list[str]:
    """Split text preferring line boundaries."""
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, limit)
        if split_at <= 0:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


# ---------------------------------------------------------------------------
# Claude CLI call (full tool access)
# ---------------------------------------------------------------------------
CLAUDE_TOOLS = "Read,Edit,Write,Grep,Glob,Bash"

def _call_claude_once(full_prompt: str, extra_flags: list[str] | None = None) -> tuple[bool, str]:
    """Single Claude CLI attempt. Returns (success, text)."""
    cmd = [
        CLAUDE_PATH,
        "-p",
        "--model", "claude-sonnet-4-6",
        "--output-format", "text",
        "--system-prompt", _build_system_prompt(),
        "--allowedTools", CLAUDE_TOOLS,
        "--permission-mode", "bypassPermissions",
        "--max-turns", "15",
    ]
    if extra_flags:
        cmd.extend(extra_flags)
    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=WORKING_DIR,
            env=_get_claude_env(),
            text=True,
            start_new_session=True,
        )
        stdout, stderr = proc.communicate(input=full_prompt, timeout=CLAUDE_TIMEOUT)

        if proc.returncode != 0:
            log.error("Claude exited %d: %s", proc.returncode, stderr.strip())
            return False, ""

        answer = stdout.strip()
        if not answer:
            return False, ""
        return True, answer

    except subprocess.TimeoutExpired:
        if proc:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                try:
                    proc.kill()
                except (ProcessLookupError, PermissionError):
                    pass
            try:
                proc.wait(timeout=5)
            except (ChildProcessError, subprocess.TimeoutExpired):
                pass
        log.warning("Claude timed out after %d sec", CLAUDE_TIMEOUT)
        return False, "TIMEOUT"

    except Exception as e:
        log.error("Claude call error: %s", e)
        return False, ""


def _call_claude_sync(full_prompt: str, extra_flags: list[str] | None = None) -> tuple[bool, str]:
    """Blocking Claude CLI call with 1 retry. Returns (success, text)."""
    for attempt in range(2):
        ok, text = _call_claude_once(full_prompt, extra_flags=extra_flags)
        if ok:
            return True, text
        if text == "TIMEOUT":
            return False, "Таймаут (1 час). Задача оказалась слишком объёмной. Попробуй разбить на части."
        if attempt == 0:
            log.info("Claude attempt 1 failed, retrying in 3 sec...")
            time.sleep(3)

    return False, "Произошла ошибка при обработке запроса. Попробуй ещё раз через минуту."


async def ask_claude(user_text: str, image_path: str | None = None) -> tuple[bool, str]:
    """Returns (success, answer_text). If image_path is set, Claude will read the image."""
    hist = history_prompt()
    full_prompt = ""
    if hist:
        full_prompt += f"История диалога:\n{hist}\n\n"

    if image_path:
        caption = user_text or "Опиши что на этом изображении"
        full_prompt += (
            f"Пользователь отправил изображение. "
            f"Прочитай файл {image_path} с помощью инструмента Read (это изображение, Read умеет их показывать). "
            f"Затем ответь на запрос пользователя.\n\n"
            f"Пользователь: {caption}"
        )
    else:
        full_prompt += f"Пользователь: {user_text}"

    if len(full_prompt) > MAX_PROMPT_CHARS:
        # Сохраняем текущий запрос пользователя, обрезаем старую историю
        if hist:
            user_part = full_prompt[len(hist):]
            max_hist = MAX_PROMPT_CHARS - len(user_part)
            if max_hist > 0:
                full_prompt = hist[-max_hist:] + user_part
            else:
                full_prompt = user_part[-MAX_PROMPT_CHARS:]
        else:
            full_prompt = full_prompt[-MAX_PROMPT_CHARS:]
        log.warning("Prompt truncated to %d chars", len(full_prompt))

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _claude_executor,
        lambda: _call_claude_sync(full_prompt),
    )


# ---------------------------------------------------------------------------
# Access check
# ---------------------------------------------------------------------------
def is_allowed(update: Update) -> bool:
    return update.effective_user and update.effective_user.id == ALLOWED_USER


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    await update.message.reply_text(
        "Привет! Я Василий — профессиональный крипто-трейдер.\n"
        "Торгую на Hyperliquid perpetual futures.\n\n"
        "Команды:\n"
        "/portfolio — портфель и P&L\n"
        "/scan — полный скан (Hyperliquid + TA + Claude)\n"
        "/ta — быстрый тех.анализ (RSI, MACD, EMA, Bollinger)\n"
        "/funding — funding rates и OI с Hyperliquid\n"
        "/daily — P&L за последние 7 дней\n"
        "/stats — win rate, profit factor, статистика\n"
        "/history — история сканов\n"
        "/status — статус бота\n"
        "/clear — очистить историю"
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    uptime = datetime.now() - START_TIME
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    await update.message.reply_text(
        f"Василий онлайн\n"
        f"PID: {os.getpid()}\n"
        f"Uptime: {hours}ч {minutes}м {seconds}с\n"
        f"Сообщений в истории: {len(user_history)}"
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    user_history.clear()
    _save_history()
    await update.message.reply_text("История очищена.")


async def cmd_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current portfolio with P&L."""
    if not is_allowed(update):
        return
    p = _load_portfolio()
    lines = [f"Портфель Василия\n"]
    lines.append(f"Начальный капитал: ${p.get('initial_capital', 100):.2f}")
    lines.append(f"Кэш: ${p.get('cash', 0):.2f}\n")

    if p.get("positions"):
        lines.append("Открытые позиции:")
        for pos in p["positions"]:
            entry = pos.get("entry", pos.get("entry_price", 0))
            sl = pos.get("stop_loss")
            tp = pos.get("take_profit")
            lines.append(
                f"  {pos.get('side','LONG')} {pos['asset']}: "
                f"${pos.get('size_usd',0):.0f} @ ${entry:.2f}"
            )
            if sl and tp:
                lines.append(f"    SL: ${sl:.2f} | TP: ${tp:.2f}")
            else:
                lines.append(f"    ⚠️ Stop Loss / Take Profit не установлены!")
            if pos.get("opened_at"):
                lines.append(f"    Открыто: {pos['opened_at'][:10]}")
    else:
        lines.append("Нет открытых позиций")

    closed = p.get("closed_trades", [])
    if closed:
        total_pnl = sum(t.get("pnl_usd", 0) for t in closed)
        wins = sum(1 for t in closed if t.get("pnl_usd", 0) > 0)
        lines.append(f"\nЗакрытые сделки: {len(closed)} (W:{wins} L:{len(closed)-wins})")
        lines.append(f"Общий PnL закрытых: ${total_pnl:+.2f}")

    scans = p.get("scan_history", [])
    if scans:
        last = scans[-1]
        lines.append(f"\nПоследний скан: {last.get('time', '?')[:16]}")
        lines.append(f"Стоимость портфеля: ${last.get('portfolio_value', '?')}")

    await update.message.reply_text("\n".join(lines))


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show last 5 scan history entries."""
    if not is_allowed(update):
        return
    p = _load_portfolio()
    scans = p.get("scan_history", [])
    if not scans:
        await update.message.reply_text("Нет истории сканов.")
        return

    lines = ["Последние сканы:\n"]
    for s in scans[-5:]:
        t = s.get("time", "?")[:16]
        val = s.get("portfolio_value", "?")
        pnl = s.get("pnl", 0)
        sent = s.get("sentiment", "?")
        actions = s.get("actions_taken", 0)
        lines.append(f"{t} | ${val} ({pnl:+.2f}$) | {sent} | действий: {actions}")
        if s.get("summary"):
            lines.append(f"  {s['summary'][:100]}")

    await update.message.reply_text("\n".join(lines))


async def cmd_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """P&L за последние 7 дней."""
    if not is_allowed(update):
        return
    pnl_path = SCRIPT_DIR / "data" / "daily_pnl.json"
    if not pnl_path.exists():
        await update.message.reply_text("Нет данных по дневному P&L. Данные появятся после первых закрытых сделок.")
        return
    try:
        snapshots = json.loads(pnl_path.read_text())
    except (json.JSONDecodeError, OSError):
        await update.message.reply_text("Ошибка чтения daily_pnl.json")
        return

    last7 = snapshots[-7:]
    if not last7:
        await update.message.reply_text("Нет записей.")
        return

    lines = ["📊 P&L за последние дни:\n"]
    lines.append(f"{'Дата':<12} {'Баланс':>8} {'P&L':>8} {'%':>6} {'Сделок':>6}")
    lines.append("─" * 44)
    for s in last7:
        pnl_str = f"{s['pnl_day']:+.2f}"
        lines.append(
            f"{s['date']:<12} ${s['balance']:>7.2f} {pnl_str:>8} {s['pnl_pct']:>+5.1f}% {s['trades']:>5}"
        )

    total_pnl = sum(s["pnl_day"] for s in last7)
    lines.append("─" * 44)
    lines.append(f"Итого P&L: ${total_pnl:+.2f}")
    await update.message.reply_text(f"```\n{chr(10).join(lines)}\n```", parse_mode="Markdown")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Win rate, средний профит/убыток, profit factor."""
    if not is_allowed(update):
        return
    p = _load_portfolio()
    closed = p.get("closed_trades", [])
    if not closed:
        await update.message.reply_text("Нет закрытых сделок для статистики.")
        return

    wins = [t for t in closed if t.get("pnl_usd", 0) > 0]
    losses = [t for t in closed if t.get("pnl_usd", 0) <= 0]
    total = len(closed)
    win_rate = len(wins) / total * 100

    avg_win = sum(t["pnl_usd"] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t["pnl_usd"] for t in losses) / len(losses) if losses else 0
    gross_profit = sum(t["pnl_usd"] for t in wins)
    gross_loss = abs(sum(t["pnl_usd"] for t in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    total_pnl = sum(t.get("pnl_usd", 0) for t in closed)

    lines = [
        "📈 Статистика торговли\n",
        f"Всего сделок: {total}",
        f"Выигрышных: {len(wins)} | Убыточных: {len(losses)}",
        f"Win Rate: {win_rate:.1f}%\n",
        f"Средний профит: ${avg_win:+.2f}",
        f"Средний убыток: ${avg_loss:+.2f}",
        f"Profit Factor: {profit_factor:.2f}",
        f"\nОбщий P&L: ${total_pnl:+.2f}",
    ]
    await update.message.reply_text("\n".join(lines))


async def daily_snapshot_job(context: ContextTypes.DEFAULT_TYPE):
    """Ежедневный snapshot баланса (раз в 24 часа)."""
    try:
        from trading_execution import get_executor
        executor = get_executor()
        if hasattr(executor, '_trader') and hasattr(executor._trader, 'save_daily_snapshot'):
            executor._trader.save_daily_snapshot()
            log.info("Daily snapshot job executed")
    except Exception as e:
        log.error("Daily snapshot job failed: %s", e)


# ---------------------------------------------------------------------------
# Periodic market scan job (runs every 3 hours)
# ---------------------------------------------------------------------------
async def periodic_scan_job(context: ContextTypes.DEFAULT_TYPE):
    """Запускает market_scan.py каждые 3 часа и отправляет отчёт в Telegram."""
    log.info("Periodic scan job started (3h interval)")
    try:
        scan_script = str(SCRIPT_DIR / "market_scan.py")
        proc = await asyncio.create_subprocess_exec(
            sys.executable, scan_script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(SCRIPT_DIR),
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        except asyncio.TimeoutError:
            proc.kill()
            log.error("Periodic scan job timed out after 5 min")
            await context.bot.send_message(
                chat_id=CHAT_ID,
                text="⚠️ Вася: плановый скан рынка завис (>5 мин), завершён принудительно."
            )
            return
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace")[:500]
            log.error("Periodic scan failed (rc=%d): %s", proc.returncode, err)
            await context.bot.send_message(
                chat_id=CHAT_ID,
                text=f"⚠️ Вася: плановый скан завершился с ошибкой.\n<code>{err}</code>",
                parse_mode="HTML"
            )
        else:
            log.info("Periodic scan completed successfully")
    except Exception as e:
        log.error("Periodic scan job error: %s", e, exc_info=True)


async def cmd_ta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show quick technical analysis for top coins."""
    if not is_allowed(update):
        return
    await update.message.reply_text("Считаю тех.анализ...")

    async def _run_ta():
        try:
            from hyperliquid_api import fetch_candles
            from technical_analysis import full_analysis, format_ta_report
            import time as _time

            coins = ["BTC", "ETH", "SOL", "BNB", "AVAX"]
            reports = []
            for coin in coins:
                candles = fetch_candles(coin, "1h", 100)
                if candles and len(candles) >= 30:
                    ta = full_analysis(candles)
                    if ta:
                        reports.append(format_ta_report(coin, ta))
                _time.sleep(0.2)

            if reports:
                text = "📊 ТЕХНИЧЕСКИЙ АНАЛИЗ (1h свечи Hyperliquid)\n\n" + "\n\n".join(reports)
            else:
                text = "Не удалось получить данные для тех.анализа."

            for chunk in _split_message(text):
                try:
                    await update.message.reply_text(chunk)
                except Exception as e:
                    log.error("TA send error: %s", e)
        except Exception as e:
            log.error("cmd_ta error: %s", e, exc_info=True)
            await update.message.reply_text(f"Ошибка тех.анализа: {e}")

    asyncio.create_task(_run_ta())


async def cmd_funding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current Hyperliquid funding rates."""
    if not is_allowed(update):
        return
    await update.message.reply_text("Получаю funding rates с Hyperliquid...")

    async def _run_funding():
        try:
            from hyperliquid_api import fetch_market_summary

            data = fetch_market_summary(["BTC", "ETH", "SOL", "BNB", "AVAX", "XRP", "LINK", "DOGE", "SUI", "ARB"])
            if not data:
                await update.message.reply_text("Не удалось получить данные с Hyperliquid.")
                return

            lines = ["📡 HYPERLIQUID — Funding & Market Data\n"]
            for coin in sorted(data.keys(), key=lambda c: -data[c]["day_volume_usd"]):
                info = data[coin]
                fr = info["funding_rate"]
                ann = info.get("funding_annual", 0)
                oi = info["open_interest_usd"]
                vol = info["day_volume_usd"]
                ch = info["price_change_24h"]
                spread = info.get("spread_pct", 0)
                imb = info.get("book_imbalance", 0)

                fr_emoji = "🔴" if abs(fr) > 0.01 else "🟡" if abs(fr) > 0.005 else "🟢"

                lines.append(
                    f"{coin}: ${info['price']:,.2f} ({ch:+.1f}%)\n"
                    f"  {fr_emoji} Funding: {fr:+.4f}% (ann: {ann:+.1f}%)\n"
                    f"  OI: ${oi/1e6:.0f}M | Vol: ${vol/1e6:.0f}M"
                    + (f" | Spread: {spread:.4f}%" if spread > 0 else "")
                    + (f" | Book: {imb:+.0f}%" if abs(imb) > 5 else "")
                )

            text = "\n".join(lines)
            for chunk in _split_message(text):
                try:
                    await update.message.reply_text(chunk)
                except Exception as e:
                    log.error("Funding send error: %s", e)
        except Exception as e:
            log.error("cmd_funding error: %s", e, exc_info=True)
            await update.message.reply_text(f"Ошибка: {e}")

    asyncio.create_task(_run_funding())


async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Trigger manual market scan."""
    if not is_allowed(update):
        return
    await update.message.reply_text("🔍 Запускаю скан v3 (Hyperliquid Extended + TA)... Результат придёт через 1-2 мин.")

    async def _run_scan():
        try:
            scan_script = str(SCRIPT_DIR / "market_scan.py")
            proc = await asyncio.create_subprocess_exec(
                sys.executable, scan_script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(SCRIPT_DIR.parent),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=180)
            if proc.returncode != 0:
                log.error("Scan failed: %s", stderr.decode()[:500])
                await update.message.reply_text("Скан завершился с ошибкой. Проверь логи.")
        except asyncio.TimeoutError:
            await update.message.reply_text("Скан превысил таймаут (3 мин).")
        except Exception as e:
            log.error("Scan error: %s", e)
            await update.message.reply_text(f"Ошибка скана: {e}")

    asyncio.create_task(_run_scan())


async def _process_single_message(update: Update, user_text: str, is_photo: bool = False, image_path: str | None = None):
    """Process a single message from the queue."""
    thinking_msg = None
    status_task = None
    try:
        thinking_msg = await update.message.reply_text("Думаю..." if not is_photo else "Смотрю скрин...")

        async def _status_updater():
            msgs = [
                "Ещё работаю, задача объёмная...",
                "Продолжаю анализ...",
                "Почти готово, финализирую...",
                "Всё ещё работаю над задачей...",
            ]
            i = 0
            while True:
                await asyncio.sleep(120)
                try:
                    await update.message.reply_text(msgs[i % len(msgs)])
                except Exception:
                    pass
                i += 1

        status_task = asyncio.create_task(_status_updater())

        user_history.append({"role": "user", "text": user_text[:2000]})
        _log_conversation("user", user_text, update.effective_user.id)

        if is_photo and image_path:
            caption = update.message.caption or ""
            success, answer = await ask_claude(caption, image_path=image_path)
        else:
            success, answer = await ask_claude(user_text)

        if success:
            user_history.append({"role": "assistant", "text": answer[:2000]})
            _log_conversation("assistant", answer, update.effective_user.id)
        else:
            _log_conversation("error", answer or "no response", update.effective_user.id)
        _save_history()

        try:
            await thinking_msg.delete()
        except Exception:
            pass

        chunks = _split_message(answer)
        if not chunks:
            await update.message.reply_text("Не получил ответ. Попробуй ещё раз.")
        else:
            for chunk in chunks:
                try:
                    await update.message.reply_text(chunk)
                except Exception as e:
                    log.error("Send error: %s", e)
                    break

    except Exception as e:
        log.error("_process_single_message error: %s", e, exc_info=True)
        try:
            if thinking_msg:
                await thinking_msg.delete()
        except Exception:
            pass
        try:
            await update.message.reply_text("Произошла ошибка, попробуй ещё раз.")
        except Exception:
            pass
    finally:
        if status_task:
            status_task.cancel()
        # Clean up temp photo file
        if image_path:
            try:
                os.unlink(image_path)
            except OSError:
                pass


async def _queue_worker():
    """Process messages from the queue one by one."""
    global _processing
    while _message_queue:
        item = _message_queue.popleft()
        async with _processing_lock:
            _processing = True
        try:
            await _process_single_message(**item)
        finally:
            async with _processing_lock:
                _processing = False
    # Reset queue task reference
    global _queue_task
    _queue_task = None


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    user_text = update.message.text
    if not user_text:
        return

    log.info("Message from %s: %.100s", update.effective_user.id, user_text)

    # Add to queue
    _message_queue.append({
        "update": update,
        "user_text": user_text,
    })

    # If queue has more than 1 item, notify user
    if len(_message_queue) > 1:
        remaining = len(_message_queue) - 1
        try:
            await update.message.reply_text(f"Ещё {remaining} в очереди, обрабатываю...")
        except Exception:
            pass

    # Start worker if not running
    global _queue_task
    if _queue_task is None or _queue_task.done():
        _queue_task = asyncio.create_task(_queue_worker())


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photos/screenshots — download, save to temp, add to queue."""
    if not is_allowed(update):
        return

    log.info("Photo from %s", update.effective_user.id)

    try:
        # Get highest resolution photo
        photo = update.message.photo[-1]
        tg_file = await photo.get_file()

        # Save to temp file in working dir
        suffix = ".jpg"
        fd, tmp_path = tempfile.mkstemp(dir=SCRIPT_DIR, suffix=suffix, prefix="vasily_photo_")
        os.close(fd)
        await tg_file.download_to_drive(tmp_path)
        log.info("Photo saved to %s (%d bytes)", tmp_path, Path(tmp_path).stat().st_size)

        # Caption from user or default
        caption = update.message.caption or ""
        user_text = f"[скриншот] {caption}" if caption else "[скриншот]"

        # Add to queue (photo cleanup handled in _process_single_message)
        _message_queue.append({
            "update": update,
            "user_text": user_text,
            "is_photo": True,
            "image_path": tmp_path,
        })

        if len(_message_queue) > 1:
            remaining = len(_message_queue) - 1
            try:
                await update.message.reply_text(f"Ещё {remaining} в очереди, обрабатываю...")
            except Exception:
                pass

        global _queue_task
        if _queue_task is None or _queue_task.done():
            _queue_task = asyncio.create_task(_queue_worker())

    except Exception as e:
        log.error("handle_photo error: %s", e, exc_info=True)
        try:
            await update.message.reply_text("Не удалось загрузить скриншот. Попробуй ещё раз.")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    err = context.error
    if isinstance(err, Conflict):
        log.critical("409 Conflict — another bot instance is running! Sending SIGTERM for graceful shutdown.")
        # Do NOT sys.exit() — that skips atexit handlers (history save, executor shutdown).
        # SIGTERM triggers PTB's shutdown path and atexit cleanly.
        os.kill(os.getpid(), signal.SIGTERM)
    elif isinstance(err, (NetworkError, TimedOut)):
        log.warning("Telegram network error (will retry): %s", err)
    else:
        log.error("Update error: %s", err, exc_info=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def _cleanup():
    """Clean up resources on exit."""
    global _lock_fd
    log.info("Cleaning up resources...")
    _save_history()
    _claude_executor.shutdown(wait=True, cancel_futures=True)
    try:
        if _lock_fd and not _lock_fd.closed:
            _lock_fd.close()
    except Exception:
        pass
    # Don't delete PID_FILE — LaunchAgent restarts immediately,
    # and cron needs the PID to detect the bot between restarts.
    # Don't delete LOCK_FILE — fcntl auto-releases on process exit.
    # Deleting it creates a race where a new instance starts before lock is freed.


async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /mode — показать или переключить режим торговли (paper/real)."""
    if not _check_user(update):
        return
    try:
        from trading_execution import get_executor
        executor = get_executor()
        status = executor.get_status()
        mode_emoji = {"paper": "\U0001f4dd", "testnet": "\U0001f9ea", "mainnet": "\U0001f534"}
        emoji = mode_emoji.get(status["mode"], "\u2753")
        msg = (
            f"{emoji} **Режим:** `{status['mode']}`\n"
            f"\U0001f4b0 Баланс: `${status['balance']:.2f}`\n"
            f"\U0001f4ca Открытых позиций: `{status['open_positions']}`\n"
            f"\n**Risk Manager:**\n"
            f"  Дневной лимит убытков: `{status['risk']['daily_loss_limit']}`\n"
            f"  Макс размер позиции: `{status['risk']['max_position_size']}`\n"
            f"  Макс позиций: `{status['risk']['max_positions']}`\n"
            f"  Emergency stop: `{status['risk']['emergency_stop']}`\n"
            f"  Дневной PnL: `${status['risk']['daily_pnl']}`\n"
            f"  Emergency: `{'ДА' if status['risk']['emergency_triggered'] else 'нет'}`"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        log.error("cmd_mode error: %s", e)
        await update.message.reply_text(f"Ошибка: {e}")


def main():
    if not BOT_TOKEN:
        log.error("VASILY_BOT_TOKEN not set in .env")
        sys.exit(1)

    if not Path(CLAUDE_PATH).exists():
        log.error("Claude CLI not found at %s", CLAUDE_PATH)
        sys.exit(1)

    atexit.register(_cleanup)

    acquire_lock()
    write_pid()
    write_heartbeat()
    _load_history()

    log.info("Василий starting, PID %d", os.getpid())

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .build()
    )

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("portfolio", cmd_portfolio))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("ta", cmd_ta))
    app.add_handler(CommandHandler("funding", cmd_funding))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("daily", cmd_daily))
    app.add_handler(CommandHandler("stats", cmd_stats))

    # Text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Photos / screenshots
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Error handler
    app.add_error_handler(error_handler)

    # Heartbeat every 60 sec
    app.job_queue.run_repeating(heartbeat_job, interval=60, first=10)

    # Daily snapshot — раз в 24 часа
    app.job_queue.run_repeating(daily_snapshot_job, interval=86400, first=60)

    # Periodic market scan + report — каждые 3 часа
    app.job_queue.run_repeating(periodic_scan_job, interval=10800, first=300)

    log.info("Василий polling started")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()
