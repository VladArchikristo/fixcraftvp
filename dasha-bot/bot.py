#!/usr/bin/env python3
"""
Даша — элитный маркетинг-бот (Telegram).
Singleton, heartbeat, Claude CLI (Sonnet), persistent history.
"""
from __future__ import annotations

import atexit
import os
import sys
import fcntl
import signal
import time
import logging
import subprocess
import asyncio
import base64
import json
import mimetypes
import tempfile
from pathlib import Path
from datetime import datetime
from collections import deque
from concurrent.futures import ThreadPoolExecutor

# Shared memory
sys.path.insert(0, '/Users/vladimirprihodko/Папка тест/fixcraftvp/shared-memory')
from shared_memory import save_message, get_history as sm_get_history, clear_history as sm_clear_history, save_fact, get_facts, build_memory_prompt, save_session_summary
from fact_extractor import extract_facts_from_exchange

from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import Conflict, NetworkError, TimedOut
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    TypeHandler,
    filters,
    ContextTypes,
)

# Суб-агенты — параллельное выполнение маленьких задач
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.subagent_utils import two_pass_call, DELEGATION_INSTRUCTIONS
from shared.agent_recovery_tools import list_agents, agent_status, recover_agent, read_code, detect_recovery_intent

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")

BOT_TOKEN = os.getenv("DASHA_BOT_TOKEN", "")
ALLOWED_USER = 244710532
CLAUDE_PATH = "/Users/vladimirprihodko/.local/bin/claude"
WORKING_DIR = "/Users/vladimirprihodko/Папка тест/fixcraftvp/"
OPENAI_BASE_URL = "http://127.0.0.1:10531/v1"
OPENAI_MODEL = "gpt-5.5"
OPENAI_TIMEOUT = 900  # 15 min — extended for complex marketing tasks
OCR_SCRIPT = Path.home() / "Папка тест/fixcraftvp/shared/apple_vision_ocr.swift"

MAX_PROMPT_CHARS = 60000  # Max prompt length for GPT-5.5

LOG_DIR = Path.home() / "logs"
LOG_DIR.mkdir(exist_ok=True)
PID_FILE = LOG_DIR / "dasha-bot.pid"
HEARTBEAT_FILE = LOG_DIR / "dasha-heartbeat"
LOCK_FILE = LOG_DIR / "dasha-bot.lock"


# OpenAI client (via openai-oauth proxy for GPT-5.5)
openai_client = None
def get_openai_client():
    global openai_client
    if openai_client is None:
        openai_client = OpenAI(base_url=OPENAI_BASE_URL, api_key="not-needed")
    return openai_client


def _call_gpt55_once(full_prompt: str, system: str) -> tuple[bool, str]:
    """Single call to GPT-5.5 via openai-oauth proxy."""
    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": full_prompt[:MAX_PROMPT_CHARS]},
            ],
            temperature=0.7,
            max_tokens=4096,
        )
        
        if response.choices and len(response.choices) > 0:
            return True, response.choices[0].message.content
        else:
            log.warning("GPT-5.5 returned no choices")
            return False, "Error: GPT-5.5 returned no response"
            
    except Exception as e:
        log.error("GPT-5.5 call failed: %s", e)
        return False, f"Error: {str(e)}"


SYSTEM_PROMPT = (
    "Ты Даша — элитный маркетолог с 15-летним опытом. "
    "Используешь GPT-5.5 через локальный openai-oauth proxy. "
    "Специализируешься на SEO, копирайтинге, контент-маркетинге, "
    "психологии продаж, email-маркетинге и social media. "
    "Даёшь конкретные, actionable советы. "
    "Говоришь профессионально но дружелюбно.\n\n"
    "== КОМАНДА НА MAC MINI ==\n"
    "Ты часть команды ботов Владимира. Любой бот может обратиться к любому другому:\n\n"
    "• Костя (@KostyaCoderBot) — программист-архитектор.\n"
    "  echo 'задача' | bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-kostya.sh'\n\n"
    "• Мыслитель Филип — промт-инженер, полиглот.\n"
    "  echo 'задача' | bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-philip.sh'\n\n"
    "• Василий (@vasily_trader_bot) — трейдер, финансовый аналитик.\n"
    "  echo 'вопрос' | bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-vasily.sh'\n\n"
    "• Доктор Пётр — медицинский агент.\n"
    "  echo 'вопрос' | bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-peter.sh'\n\n"
    "• Зина — астролог и нумеролог.\n"
    "  echo 'вопрос' | bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-zina.sh'\n\n"
    "• Beast (@Antropic_BeastBot) — главный ассистент Владимира.\n\n"
    "НЕЛЬЗЯ ТРОГАТЬ: beast-bot/bot.py, .env файлы, launcher.sh скрипты.\n\n"
"== ВОССТАНОВЛЕНИЕ АГЕНТОВ ==\n"
"Ты умеешь помогать Владу восстанавливать агентов через реальные команды бота:\n"
"/agents — список известных агентов и launchctl labels.\n"
"/agentstatus [agent] — статус, PID, plist, хвост логов без секретов.\n"
"/recover <agent|all> — безопасно перезапустить LaunchAgent через launchctl kickstart -k.\n"
"/readcode <agent> [query] — прочитать код агента или найти участок по query, секреты редактируются.\n"
"Если Влад пишет обычной фразой ‘восстанови Hermes/Дашу/Баху/Машу’ — используй recovery-команду, а не отвечай ‘не умею’.\n"
"Никогда не показывай токены, .env, cookie, refresh/access tokens.\n\n"
    "== OPEN DESIGN / ДИЗАЙН-СИСТЕМЫ ==\n"
    "У тебя есть локальный Open Design слой: /Users/vladimirprihodko/ai-tools/open-design. "
    "Используй его для задач дизайна, лендингов, UI, презентаций, постеров, соцсетей, рекламных креативов и visual QA. "
    "Не придумывай дизайн с нуля, если можно опереться на Open Design skill + design system. "
    "Сначала выбирай: artifact type, design skill, design system, аудитория, conversion goal, mobile/desktop. "
    "Доступные типы: saas-landing, web-prototype, dashboard, mobile-app, mobile-onboarding, pricing-page, docs-page, blog-post, email-marketing, social-carousel, magazine-poster, motion-frames, guizang-ppt/simple-deck. "
    "Дизайн-системы: apple, stripe, linear, vercel, airbnb, notion, canva, coinbase, clean, corporate, brutalism и другие из design-systems. "
    "Для FixCraft VP чаще выбирай premium contractor trust style: clean/stripe/linear/apple, mobile-first, lead-capture first, реальные trust блоки, no AI-slop. "
    "Картинки делай как арт-директор: композиция, палитра, свет, типографический вайб, формат, negative space, требования к тексту отдельно. "
    "Если нужен точный текст на картинке — предложи генерировать фон отдельно и накладывать текст через HTML/SVG, потому что image models часто ломают буквы. "
    "Качество проверяй по чеклисту: hierarchy, spacing, typography, contrast, conversion, production feasibility. "
    "Не запускай OpenRouter и платные fallback без разрешения Влада.\n\n"
    "== СКРИНШОТЫ И КАРТИНКИ ==\n"
    "Если Влад присылает скриншот/фото — ты обязана реально читать изображение, а не говорить 'не могу'. "
    "Опиши что видишь: текст, кнопки, цвета, layout, ошибки, важные детали. "
    "Если качество плохое — всё равно извлеки максимум и только потом попроси более чёткий скрин. "
    "Для смет FixCraft сначала опиши видимые повреждения/работы, потом считай цену.\n\n"
    "== ДЕЛЕГИРОВАНИЕ СУБ-АГЕНТАМ ==\n"
    "Используй команду активно — не делай сама то, что лучше сделает специалист.\n\n"
    "КОГДА делегировать:\n"
    "- Нужен код, скрипт, техническое решение → Костя\n"
    "- Нужен финансовый анализ, трейдинг → Василий\n"
    "- Нужен промт, архитектура идеи → Филип\n"
    "- Задача независимая — запускай параллельно\n\n"
    "КАК запустить параллельно два агента:\n"
    "  RESULT1=$(bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-kostya.sh' 'задача' &)\n"
    "  RESULT2=$(bash '/Users/vladimirprihodko/Папка тест/fixcraftvp/scripts/ask-vasily.sh' 'вопрос' &)\n"
    "  wait\n\n"
    "НЕ делегируй: маркетинг, SEO, копирайт, контент — это твоя зона.\n"
    + DELEGATION_INSTRUCTIONS
)

MODE_PREFIXES = {
    "seo": "Режим SEO-анализа. Фокусируйся на поисковой оптимизации, ключевых словах, мета-тегах, технической SEO, ссылочной массе.",
    "copy": "Режим копирайтинга. Фокусируйся на написании продающих текстов, заголовков, УТП, call-to-action.",
    "psych": "Режим психологии продаж. Фокусируйся на триггерах, убеждении, социальном доказательстве, FOMO, якорении цен.",
    "content": "Режим контент-стратегии. Фокусируйся на контент-плане, форматах, дистрибуции, воронках контента.",
    "social": "Режим social media. Фокусируйся на SMM-стратегии, вовлечённости, рекламе в соцсетях, визуальном контенте.",
    "email": "Режим email-маркетинга. Фокусируйся на рассылках, автоворонках, сегментации, open rate, конверсиях.",
    "launch": "Режим запуска продукта. Фокусируйся на launch-стратегии, pre-launch, GTM, позиционировании.",
    "cro": "Режим оптимизации конверсий. Фокусируйся на A/B тестах, UX, посадочных страницах, воронках.",
    "strategy": "Режим маркетинговой стратегии. Фокусируйся на общей стратегии, позиционировании, конкурентном анализе, бюджетах.",
    "ideas": "Режим брейнсторма. Генерируй креативные идеи, нестандартные подходы, growth hacks.",
    "audit": "Режим маркетингового аудита. Проведи комплексный анализ маркетинга: сайт, SEO, контент, соцсети, реклама.",
    "estimate": """Режим СМЕТЧИК — ты составляешь сметы на ремонтные работы для FixCraftVP Handyman Services (Charlotte, NC).

ТВОЯ ЗАДАЧА:
Когда пользователь присылает фото + описание — проанализируй и составь смету.

ФОРМАТ СМЕТЫ:
1. **Что вижу на фото** — кратко опиши проблему/состояние
2. **Список работ** — каждая позиция отдельно
3. **Смета** — таблица с ценами
4. **ИТОГО** — диапазон мин-макс
5. **Примечания** — что может изменить цену

ПРАЙС-ЛИСТ Charlotte NC (labor only, materials extra) — +15% выше рынка (FixCraft premium):

🎨 ПОКРАСКА:
- Покраска стен (за комнату 12x12): $175–$290
- Покраска потолка: $115–$210
- Покраска внешняя (фасад, 1 стена): $300–$600
- Покраска кабинетов/шкафов: $400–$900
- Покраска забора (за 50 фут): $150–$300
- Покраска гаражных ворот: $120–$250
- Покраска лестницы/перил: $100–$200
- Текстурирование стен/потолка: $150–$350
- Грунтовка стен перед покраской: $80–$150
- Покраска палубы/террасы (за 200 кв.фут): $200–$450

🔌 ЭЛЕКТРИКА:
- Замена розетки/выключателя: $85–$140
- Установка светильника: $90–$175
- Установка потолочного вентилятора: $125–$230
- Установка диммера: $80–$150
- Замена автомата в щитке: $120–$220
- Установка GFCI розетки (ванна/кухня): $90–$160
- Монтаж наружного освещения: $120–$200
- Прокладка кабеля (за 10 фут): $80–$150
- Установка детектора дыма/CO: $60–$100
- Установка умного выключателя/диммера: $100–$180

🚿 САНТЕХНИКА:
- Замена смесителя (кухня/ванна): $115–$230
- Устранение течи под раковиной: $85–$175
- Замена туалета: $200–$400
- Замена сифона: $75–$140
- Прочистка засора: $100–$200
- Замена водонагревателя (labor only): $200–$450
- Установка фильтра воды под раковину: $100–$200
- Замена душевой лейки: $60–$120
- Силиконизация ванны/душа/раковины: $90–$175
- Ремонт арматуры в баке унитаза: $80–$150
- Установка посудомоечной машины (подключение): $150–$280

🧱 ГИПСОКАРТОН И СТЕНЫ:
- Ремонт гипсокартона (дыра до 6"): $115–$230
- Ремонт гипсокартона (большая площадь, за кв.фут): $9–$18
- Шпаклёвка и выравнивание стены: $100–$250
- Установка гипсокартона (за лист): $80–$160
- Текстура «апельсиновая корка» (за 100 кв.фут): $100–$200
- Ремонт трещин в стенах/потолке: $80–$180

🚪 ДВЕРИ И ОКНА:
- Навеска двери interior: $175–$290
- Навеска двери exterior: $200–$400
- Замена дверной ручки/замка: $70–$140
- Установка дедболта (замок): $90–$160
- Регулировка/подгонка двери (скрипит/не закрывается): $60–$130
- Установка дверного доводчика: $80–$160
- Установка экранной/mosquito door: $120–$230
- Замена уплотнителей окна/двери: $70–$140
- Установка оконных решёток: $100–$200
- Ремонт жалюзи/роллет: $60–$120
- Установка карниза для штор: $55–$115
- Замена стекла в окне: $150–$350

🪵 ПЛОТНИЦКИЕ И СТОЛЯРНЫЕ:
- Установка полок: $60–$115 за полку
- Сборка мебели (простая): $85–$175
- Сборка мебели (сложная, кухня/шкаф): $175–$400
- Установка шкафа/тумбы (крепление к стене): $100–$200
- Ремонт кухонных шкафчиков: $80–$180
- Замена фасадов шкафов: $120–$280
- Установка карниза/молдинга (за 10 фут): $80–$160
- Установка baseboards (плинтус, за 10 фут): $70–$140
- Строительство декоративной полки/ниши: $200–$500
- Монтаж деревянной перегородки: $400–$900
- Ремонт деревянной лестницы: $150–$350

🏠 ПОЛ И ПОТОЛОК:
- Укладка плитки (за кв.фут): $9–$18
- Укладка ламината/vinyl plank (за кв.фут): $4–$9
- Замена участка напольного покрытия: $115–$345
- Устранение скрипа пола: $85–$175
- Установка порогов/переходников: $60–$120
- Шлифовка деревянного пола (за комнату): $300–$600
- Укладка ковролина (за комнату): $200–$450
- Ремонт/замена потолочной плитки: $100–$200

📺 МОНТАЖ И УСТАНОВКА:
- Монтаж TV на стену: $115–$230
- Установка кронштейна TV + скрытая проводка: $175–$320
- Установка проектора: $120–$250
- Сборка и установка барбекю-гриля: $100–$200
- Установка стиральной/сушильной машины (подключение): $120–$230
- Установка холодильника со льдом (подключение воды): $100–$180
- Установка микроволновки над плитой: $120–$220
- Установка вытяжки: $150–$280
- Установка кондиционера (window unit): $120–$200
- Установка умного термостата: $100–$180
- Установка видеозвонка/домофона: $100–$200
- Установка камер безопасности (за камеру): $100–$200
- Установка полки в гараже: $80–$160

🏗️ НАРУЖНЫЕ РАБОТЫ:
- Давление воды (pressure washing, 1000 кв.фут): $150–$300
- Давление воды (подъездная дорожка): $100–$200
- Мелкий ремонт кровли (за пятно): $175–$400
- Замена водосточного желоба (за 10 фут): $115–$230
- Прочистка водостоков: $100–$200
- Ремонт палубы/terrasse (за кв.фут): $10–$20
- Покраска/обработка палубы: $300–$600
- Ремонт забора (за секцию): $100–$250
- Установка почтового ящика: $80–$160
- Ремонт дорожки/патио (за кв.фут): $10–$20
- Посев/укладка газона (за 100 кв.фут): $100–$250
- Мульчирование клумб (за 10 кв.фут): $50–$120

🔧 МЕЛКИЙ РЕМОНТ И ПРОЧЕЕ:
- Герметизация окна/двери (draft seal): $70–$140
- Устранение диагностика утечки воды: $85–$145
- Ремонт garage door (настройка, смазка): $100–$200
- Замена петель шкафов: $50–$100
- Установка поручней/grab bars в ванной: $120–$230
- Установка детских защитных барьеров: $80–$160
- Ремонт/замена почтового ящика: $60–$130
- Чистка и обслуживание вентиляции (dryer vent): $100–$180
- Дезинсекция/уплотнение щелей: $80–$160
- Генеральная уборка после ремонта: $230–$460
- Вывоз строительного мусора (за pickup truck): $150–$300

МАТЕРИАЛЫ: добавь 15-25% сверху на материалы если они нужны.

ВАЖНО:
- Давай диапазон цен, не одну цифру
- Указывай что входит в цену (labor only или с материалами)
- Если фото нечёткое — задай уточняющий вопрос
- Конечная цена зависит от осмотра на месте — всегда добавь эту оговорку
- Отвечай на том языке, на котором написан запрос (русский или английский)""",
}

START_TIME = datetime.now()
_claude_executor = ThreadPoolExecutor(max_workers=1)
_processing = False
_processing_lock = asyncio.Lock()
_processing_since: float | None = None  # timestamp when _processing became True
_WATCHDOG_TIMEOUT = 660  # 11 min — soft reset if no Claude running
_WATCHDOG_HARD_LIMIT = 720  # 12 min — hard reset even if Claude is alive
_message_queue: deque = deque(maxlen=5)  # queue up to 5 messages

# Polling health monitor — detect dead polling after Bad Gateway / network errors
_last_update_time: float = time.time()  # last time ANY update was received
_POLLING_DEAD_TIMEOUT = 3600  # 1 hour without any update = polling is dead
_polling_restart_count: int = 0


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
# Logging — stdout only (LaunchAgent redirects to ~/logs/dasha-bot.log)
# Token sanitization: never leak bot token in logs
# ---------------------------------------------------------------------------
class _SafeFormatter(logging.Formatter):
    """Replaces bot token with *** in all log output."""
    def format(self, record):
        msg = super().format(record)
        if BOT_TOKEN and len(BOT_TOKEN) > 10:
            msg = msg.replace(BOT_TOKEN, "***")
        return msg

_log_formatter = _SafeFormatter("%(asctime)s [%(levelname)s] %(message)s")
_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.setFormatter(_log_formatter)

logging.basicConfig(level=logging.INFO, handlers=[_stdout_handler])
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger("dasha")

# ---------------------------------------------------------------------------
# Singleton lock — fail immediately, no retries (prevents ghost races)
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


async def heartbeat_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        write_heartbeat()
    except Exception as e:
        log.error("Heartbeat write failed: %s", e)


async def watchdog_job(context: ContextTypes.DEFAULT_TYPE):
    """Auto-reset _processing if stuck. Soft limit 5min, hard limit 10min."""
    global _processing, _processing_since
    try:
        async with _processing_lock:
            if not _processing or _processing_since is None:
                return
            elapsed = time.time() - _processing_since
            if elapsed < _WATCHDOG_TIMEOUT:
                return

            # Find Claude child processes
            claude_pids = _find_claude_children()

            if elapsed >= _WATCHDOG_HARD_LIMIT:
                # Hard limit — kill everything, no mercy
                log.warning("Watchdog HARD LIMIT: _processing stuck %.0fs — killing Claude and resetting!", elapsed)
                _kill_claude_children(claude_pids)
                _processing = False
                _processing_since = None
                # Notify about dropped messages
                dropped = len(_message_queue)
                _message_queue.clear()
                if dropped:
                    log.warning("Watchdog: dropped %d queued messages after hard reset", dropped)
                return

            if claude_pids:
                log.info("Watchdog: _processing stuck %.0fs, Claude PIDs %s still running — waiting for hard limit", elapsed, claude_pids)
                return

            # Soft limit — no Claude running, reset
            log.warning("Watchdog: _processing stuck %.0fs with no active Claude — force reset!", elapsed)
            _processing = False
            _processing_since = None
            dropped = len(_message_queue)
            _message_queue.clear()
            if dropped:
                log.warning("Watchdog: dropped %d queued messages after soft reset", dropped)
    except Exception as e:
        log.error("Watchdog error: %s", e)


def _find_claude_children() -> list[int]:
    """Find Claude child process PIDs."""
    pids = []
    try:
        import psutil
        for child in psutil.Process(os.getpid()).children(recursive=True):
            if "claude" in child.name().lower():
                pids.append(child.pid)
    except Exception:
        try:
            result = subprocess.run(
                ["pgrep", "-P", str(os.getpid()), "-f", "claude"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().splitlines():
                    try:
                        pids.append(int(line.strip()))
                    except ValueError:
                        pass
        except Exception:
            pass
    return pids


def _kill_claude_children(pids: list[int]):
    """Kill Claude child processes by PID."""
    for pid in pids:
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
            log.info("Watchdog: killed Claude process group (PID %d)", pid)
        except (ProcessLookupError, PermissionError):
            try:
                os.kill(pid, signal.SIGKILL)
                log.info("Watchdog: killed Claude process (PID %d)", pid)
            except (ProcessLookupError, PermissionError):
                pass


# ---------------------------------------------------------------------------
# Persistent history (saved to disk, survives restarts)
# ---------------------------------------------------------------------------
HISTORY_FILE = SCRIPT_DIR / "history.json"
user_history: deque[dict] = deque(maxlen=10)

# Full conversation log (never truncated, appends forever)
CONVERSATION_LOG = SCRIPT_DIR / "conversation_log.jsonl"
CONVERSATION_LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


def _rotate_log_if_needed():
    """Rotate conversation log when it exceeds size limit."""
    try:
        if CONVERSATION_LOG.exists() and CONVERSATION_LOG.stat().st_size > CONVERSATION_LOG_MAX_BYTES:
            old = CONVERSATION_LOG.with_suffix(".jsonl.old")
            if old.exists():
                old.unlink()
            CONVERSATION_LOG.rename(old)
            log.info("Rotated conversation log (exceeded %d MB)", CONVERSATION_LOG_MAX_BYTES // (1024 * 1024))
    except Exception as e:
        log.warning("Log rotation failed: %s", e)


def _log_conversation(role: str, text: str, user_id: int | None = None):
    """Append a single message to the permanent conversation log."""
    _rotate_log_if_needed()
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


# Per-user mode (in-memory, resets on restart — that's fine)
user_modes: dict[int, str] = {}


def _load_history():
    if not HISTORY_FILE.exists():
        return
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("history is not a list")
        for item in data[-40:]:
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
    tmp_path = None
    try:
        data = json.dumps(list(user_history), ensure_ascii=False, indent=None)
        fd, tmp_path = tempfile.mkstemp(dir=SCRIPT_DIR, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp_path, str(HISTORY_FILE))
        tmp_path = None
    except Exception as e:
        log.warning("Failed to save history: %s", e)
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def history_prompt(user_id: int | None = None) -> str:
    parts = []
    # Level 2+3: долгосрочная память
    if user_id is not None:
        mem = build_memory_prompt(user_id, "dasha")
        if mem:
            parts.append(mem)
    # Level 1: последние сообщения
    if user_id is not None:
        msgs = sm_get_history(user_id, "dasha", limit=20)
        if msgs:
            parts.append("\n=== ПОСЛЕДНИЙ ДИАЛОГ ===")
            for msg in msgs:
                role = "Пользователь" if msg["role"] == "user" else "Даша"
                parts.append(f"{role}: {msg['content'][:2000]}")
            return "\n".join(parts)
    # Fallback на in-memory deque
    if not user_history:
        return "\n".join(parts) if parts else ""
    lines = []
    for msg in list(user_history)[-20:]:
        role = "Пользователь" if msg["role"] == "user" else "Даша"
        lines.append(f"{role}: {msg['text'][:2000]}")
    if lines:
        parts.append("\n=== ПОСЛЕДНИЙ ДИАЛОГ ===")
        parts.extend(lines)
    return "\n".join(parts)


async def _safe_reply(message, text: str):
    """Send with Markdown, fallback to plain text on parse error."""
    try:
        await message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.debug("Markdown parse failed, falling back to plain text: %s", e)
        await message.reply_text(text)


def _split_message(text: str, limit: int = 4096) -> list[str]:
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
# Claude CLI call (stdin-based, with clean env, full tool access)
# ---------------------------------------------------------------------------
# All calls get tool access — Claude decides if tools are needed
def _image_to_data_url(image_path: str) -> str:
    """Encode a downloaded Telegram image for GPT vision."""
    mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"
    data = Path(image_path).read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _run_apple_vision_ocr(image_path: str) -> tuple[bool, str]:
    """Local macOS OCR fallback using Apple Vision. No paid API."""
    try:
        if not OCR_SCRIPT.exists():
            return False, f"OCR script not found: {OCR_SCRIPT}"
        result = subprocess.run(
            ["/usr/bin/swift", str(OCR_SCRIPT), image_path],
            capture_output=True,
            text=True,
            timeout=90,
        )
        if result.returncode != 0:
            return False, (result.stderr or result.stdout or "Apple Vision OCR failed").strip()
        return True, result.stdout.strip()
    except Exception as e:
        return False, str(e)


def _call_gpt55_with_ocr(full_prompt: str, system: str, image_path: str) -> tuple[bool, str]:
    ok, ocr_text = _run_apple_vision_ocr(image_path)
    if not ok:
        return False, f"Vision proxy упал и OCR fallback тоже не сработал: {ocr_text}"
    prompt = full_prompt or "Объясни, что на скриншоте/фото по OCR-тексту."
    combined = (
        f"Пользователь прислал скриншот/фото. GPT-vision через proxy недоступен, поэтому ниже OCR Apple Vision.\n\n"
        f"Задача пользователя: {prompt}\n\n"
        f"OCR-текст со скриншота:\n```\n{ocr_text or '[OCR не нашёл текста]'}\n```\n\n"
        "Сделай полезный вывод: что это за экран, что важно, есть ли ошибки/лимиты/статусы, что делать дальше. "
        "Если OCR неполный — честно отметь это."
    )
    return _call_gpt55_once(combined, system)


def _call_gpt55_vision_once(full_prompt: str, system: str, image_path: str) -> tuple[bool, str]:
    """Single GPT-5.5 vision call via openai-oauth proxy, with local OCR fallback."""
    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": (full_prompt or "Прочитай скриншот/фото и опиши всё важное.")[:MAX_PROMPT_CHARS]},
                        {"type": "image_url", "image_url": {"url": _image_to_data_url(image_path)}},
                    ],
                },
            ],
            temperature=0.4,
            max_tokens=4096,
        )
        if response.choices and len(response.choices) > 0:
            return True, response.choices[0].message.content
        return False, "Error: GPT-5.5 vision returned no response"
    except Exception as e:
        log.warning("GPT-5.5 vision call failed, trying Apple Vision OCR fallback: %s", e)
        return _call_gpt55_with_ocr(full_prompt, system, image_path)


def _call_gpt55_sync(full_prompt: str, system: str, image_path: str | None = None) -> tuple[bool, str]:
    """Call GPT-5.5 with retry (text or vision, no Claude)."""
    for attempt in range(3):
        if image_path:
            ok, text = _call_gpt55_vision_once(full_prompt, system, image_path)
        else:
            ok, text = _call_gpt55_once(full_prompt, system)
        if ok:
            return True, text
        if attempt < 2:
            time.sleep(1)
    return False, "Произошла ошибка при обработке запроса (3 попытки). Попробуй ещё раз через минуту."


def build_system_prompt(user_id: int) -> str:
    mode = user_modes.get(user_id)
    if mode and mode in MODE_PREFIXES:
        return f"{MODE_PREFIXES[mode]}\n\n{SYSTEM_PROMPT}"
    return SYSTEM_PROMPT


async def ask_gpt55(user_text: str, user_id: int, image_path: str | None = None) -> tuple[bool, str]:
    """Ask GPT-5.5 via openai-oauth proxy."""
    try:
        loop = asyncio.get_event_loop()
        system = build_system_prompt(user_id)
        return await loop.run_in_executor(
            _claude_executor,
            lambda: _call_gpt55_sync(user_text, system, image_path=image_path),
        )
    except Exception as e:
        log.error("ask_gpt55 error: %s", e)
        return False, f"Error: {str(e)}"
def is_allowed(update: Update) -> bool:
    return update.effective_user and update.effective_user.id == ALLOWED_USER


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    await update.message.reply_text(
        "Привет! Я Даша — твой элитный маркетолог.\n\n"
        "Я специализируюсь на:\n"
        "- SEO и поисковой оптимизации\n"
        "- Копирайтинге и продающих текстах\n"
        "- Контент-маркетинге\n"
        "- Психологии продаж\n"
        "- Email-маркетинге\n"
        "- Social media\n\n"
        "Команды:\n"
        "/seo — режим SEO-анализа\n"
        "/copy — режим копирайтинга\n"
        "/psych — психология продаж\n"
        "/content — контент-стратегия\n"
        "/social — social media\n"
        "/email — email-маркетинг\n"
        "/launch — запуск продукта\n"
        "/cro — оптимизация конверсий\n"
        "/strategy — маркетинговая стратегия\n"
        "/ideas — брейнсторм идей\n"
        "/audit — маркетинговый аудит\n"
        "/estimate — 🔨 СМЕТЧИК (фото + описание → смета)\n"
        "/clear — очистить историю\n"
        "/status — статус бота\n"
        "/agents — список агентов\n"
        "/agentstatus [agent] — статус агента\n"
        "/recover <agent|all> — восстановить агента\n"
        "/readcode <agent> [query] — читать код агента\n\n"
        "Задавай любой вопрос по маркетингу!\n\n"
        "💡 Для сметы ремонта: /estimate → отправь фото + описание работ"
    )


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    uptime = datetime.now() - START_TIME
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    mode = user_modes.get(update.effective_user.id, "общий")
    polling_age = int(time.time() - _last_update_time)
    restart_info = f"\nPolling restarts: {_polling_restart_count}" if _polling_restart_count > 0 else ""
    await update.message.reply_text(
        f"Даша онлайн\n"
        f"PID: {os.getpid()}\n"
        f"Аптайм: {hours}ч {minutes}м {seconds}с\n"
        f"Режим: {mode}\n"
        f"Сообщений в истории: {len(user_history)}\n"
        f"Последний update: {polling_age}с назад"
        f"{restart_info}"
    )


async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    uid = update.effective_user.id
    user_history.clear()
    _save_history()
    sm_clear_history(uid, "dasha")
    user_modes.pop(uid, None)
    await update.message.reply_text("История и режим очищены.")


async def cmd_agents(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    for chunk in _split_message(list_agents()):
        await update.message.reply_text(chunk)


async def cmd_agentstatus(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    name = ctx.args[0] if ctx.args else None
    for chunk in _split_message(agent_status(name)):
        await update.message.reply_text(chunk)


async def cmd_recover(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    target = " ".join(ctx.args).strip()
    if not target:
        await update.message.reply_text("Укажи агента: /recover hermes | dasha | masha | bakha | openai-oauth | all")
        return
    await update.message.reply_text(f"Восстанавливаю {target}...")
    result = await asyncio.get_running_loop().run_in_executor(_claude_executor, lambda: recover_agent(target))
    for chunk in _split_message(result):
        await update.message.reply_text(chunk)


async def cmd_readcode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    if not ctx.args:
        await update.message.reply_text("Формат: /readcode dasha [query] | masha | bakha")
        return
    target = ctx.args[0]
    query = " ".join(ctx.args[1:]).strip() or None
    result = await asyncio.get_running_loop().run_in_executor(_claude_executor, lambda: read_code(target, query))
    for chunk in _split_message(result):
        await update.message.reply_text(chunk)


async def cmd_deploy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    await update.message.reply_text("Запускаю деплой сайта на Vercel...")
    try:
        result = await asyncio.get_running_loop().run_in_executor(
            _claude_executor,
            lambda: subprocess.run(
                ["vercel", "--prod", "--yes"],
                cwd=str(Path(WORKING_DIR) / "site-source"),
                capture_output=True,
                text=True,
                timeout=300,
                env=_get_claude_env(),
            ),
        )
        if result.returncode == 0:
            url = ""
            for line in result.stdout.splitlines():
                if "vercel.app" in line and "http" in line:
                    url = line.strip().split()[-1] if line.strip() else ""
                    break
            msg = f"Сайт задеплоен!\n{url}" if url else "Деплой завершён успешно."
            await update.message.reply_text(msg)
        else:
            err = (result.stderr or result.stdout or "unknown error")[:500]
            await update.message.reply_text(f"Ошибка деплоя:\n{err}")
    except subprocess.TimeoutExpired:
        await update.message.reply_text("Таймаут деплоя (5 мин). Попробуй позже.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


async def cmd_set_mode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    uid = update.effective_user.id
    command = update.message.text.split()[0].lstrip("/").split("@")[0]
    if command in MODE_PREFIXES:
        user_modes[uid] = command
        await update.message.reply_text(
            f"Режим: {command.upper()}\n{MODE_PREFIXES[command]}\n\nГотова работать. Задавай вопросы!"
        )
    else:
        await update.message.reply_text("Неизвестный режим.")


async def _process_single_message(update: Update, user_text: str, image_path: str | None = None):
    """Process a single message (text or photo/screenshot) through GPT-5.5."""
    thinking_msg = None
    status_task = None
    try:
        thinking_label = "Смотрю скрин..." if image_path else "Думаю..."
        thinking_msg = await update.message.reply_text(thinking_label)

        # Periodic status updates while Claude works
        async def _status_updater():
            msgs = [
                "Ещё работаю, задача объёмная...",
                "Продолжаю, не переживай...",
                "Почти готово, финализирую...",
                "Всё ещё работаю над задачей...",
            ]
            i = 0
            while True:
                await asyncio.sleep(120)  # every 2 min
                try:
                    await update.message.reply_text(msgs[i % len(msgs)])
                except Exception:
                    pass
                i += 1

        status_task = asyncio.create_task(_status_updater())

        uid = update.effective_user.id
        if image_path:
            caption = user_text or ""
            hist_text = f"[скриншот] {caption}" if caption else "[скриншот]"
            user_history.append({"role": "user", "text": hist_text[:2000]})
            save_message(uid, "dasha", "user", hist_text[:5000])
            _log_conversation("user", hist_text, uid)
            success, answer = await ask_gpt55(caption, uid, image_path=image_path)
        else:
            user_history.append({"role": "user", "text": user_text[:2000]})
            save_message(uid, "dasha", "user", user_text[:5000])
            _log_conversation("user", user_text, uid)
            success, answer = await ask_gpt55(user_text, uid)

        if success:
            user_history.append({"role": "assistant", "text": answer[:2000]})
            _save_history()
            save_message(uid, "dasha", "assistant", answer[:5000])
            try:
                extract_facts_from_exchange(uid, "dasha", user_text, answer)
            except Exception:
                pass
            _log_conversation("assistant", answer, uid)

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
                    await _safe_reply(update.message, chunk)
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
        if image_path:
            try:
                os.unlink(image_path)
            except OSError:
                pass


async def _drain_queue(update: Update):
    """Process queued messages one by one after current message finishes."""
    global _processing, _processing_since
    while True:
        async with _processing_lock:
            if not _message_queue:
                _processing = False
                _processing_since = None
                return
            queued_update, queued_text, queued_image = _message_queue.popleft()
            _processing_since = time.time()  # refresh timer for each queued msg

        remaining = len(_message_queue)
        if remaining > 0:
            try:
                await queued_update.message.reply_text(f"В очереди ещё {remaining}. Подожди.")
            except Exception:
                pass

        try:
            await _process_single_message(queued_update, queued_text, queued_image)
        except Exception as e:
            log.error("_drain_queue: error processing queued message: %s", e, exc_info=True)
            try:
                await queued_update.message.reply_text("Ошибка при обработке сообщения из очереди. Попробуй ещё раз.")
            except Exception:
                pass


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    user_text = update.message.text
    if not user_text:
        return

    log.info("Message from %s: %.100s", update.effective_user.id, user_text)

    intent = detect_recovery_intent(user_text)
    if intent:
        action, target = intent
        if action == "recover" and target:
            await update.message.reply_text(f"Поняла. Восстанавливаю {target}...")
            result = await asyncio.get_running_loop().run_in_executor(_claude_executor, lambda: recover_agent(target))
            for chunk in _split_message(result):
                await update.message.reply_text(chunk)
            return
        if action == "readcode" and target:
            result = await asyncio.get_running_loop().run_in_executor(_claude_executor, lambda: read_code(target, None))
            for chunk in _split_message(result):
                await update.message.reply_text(chunk)
            return

    global _processing, _processing_since
    async with _processing_lock:
        if _processing:
            if len(_message_queue) >= 5:
                await update.message.reply_text("Очередь полная (5). Подожди немного.")
                return
            _message_queue.append((update, user_text, None))
            pos = len(_message_queue)
            await update.message.reply_text(f"В очереди ({pos}). Дойду скоро.")
            return
        _processing = True
        _processing_since = time.time()

    try:
        await _process_single_message(update, user_text)
        # Drain any queued messages
        await _drain_queue(update)
    except Exception as e:
        log.error("handle_message fatal error: %s", e, exc_info=True)
        async with _processing_lock:
            _processing = False
            _processing_since = None
            _message_queue.clear()
        try:
            await update.message.reply_text("Произошла критическая ошибка. Сбросила состояние, пиши снова.")
        except Exception:
            pass


async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle photos/screenshots — download, save to temp, ask GPT-5.5 vision to read."""
    if not is_allowed(update):
        return

    log.info("Photo from %s", update.effective_user.id)

    # Download photo immediately (before queueing, since Telegram file links expire)
    tmp_path = None
    try:
        photo = update.message.photo[-1]
        tg_file = await photo.get_file()
        fd, tmp_path = tempfile.mkstemp(suffix=".jpg", prefix="dasha_photo_")
        os.close(fd)
        await tg_file.download_to_drive(tmp_path)
        log.info("Photo saved to %s (%d bytes)", tmp_path, Path(tmp_path).stat().st_size)
    except Exception as e:
        log.error("Failed to download photo: %s", e)
        await update.message.reply_text("Не удалось скачать фото. Попробуй ещё раз.")
        return

    caption = update.message.caption or ""

    global _processing, _processing_since
    async with _processing_lock:
        if _processing:
            if len(_message_queue) >= 5:
                await update.message.reply_text("Очередь полная (5). Подожди немного.")
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                return
            _message_queue.append((update, caption, tmp_path))
            pos = len(_message_queue)
            await update.message.reply_text(f"В очереди ({pos}). Дойду скоро.")
            return
        _processing = True
        _processing_since = time.time()

    try:
        await _process_single_message(update, caption, image_path=tmp_path)
        await _drain_queue(update)
    except Exception as e:
        log.error("handle_photo fatal error: %s", e, exc_info=True)
        async with _processing_lock:
            _processing = False
            _processing_since = None
            _message_queue.clear()
        try:
            await update.message.reply_text("Произошла критическая ошибка. Сбросила состояние, пиши снова.")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Polling health — track updates, detect dead polling, auto-restart
# ---------------------------------------------------------------------------
async def _track_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Called on EVERY incoming update (group -1) — just bumps the timestamp."""
    global _last_update_time
    _last_update_time = time.time()


async def _polling_health_job(context: ContextTypes.DEFAULT_TYPE):
    """Every 60s check if polling is alive. If no updates for 15 min — restart."""
    global _last_update_time, _polling_restart_count
    try:
        elapsed = time.time() - _last_update_time
        if elapsed < _POLLING_DEAD_TIMEOUT:
            return

        log.warning(
            "⚠️ Polling health: no updates for %.0f sec (limit %d) — restarting polling!",
            elapsed, _POLLING_DEAD_TIMEOUT,
        )
        _polling_restart_count += 1

        # Stop and restart the updater (polling mechanism)
        if _app_ref and _app_ref.updater and _app_ref.updater.running:
            try:
                await _app_ref.updater.stop()
                log.info("Updater stopped, restarting...")
            except Exception as e:
                log.warning("Error stopping updater: %s", e)

        if _app_ref and _app_ref.updater:
            try:
                await _app_ref.updater.start_polling(
                    drop_pending_updates=False,
                    allowed_updates=Update.ALL_TYPES,
                )
                _last_update_time = time.time()  # reset timer
                log.info("✅ Polling restarted successfully (restart #%d)", _polling_restart_count)
            except Exception as e:
                log.error("Failed to restart polling: %s — will retry next cycle", e)

    except Exception as e:
        log.error("Polling health job error: %s", e)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    err = context.error
    if isinstance(err, Conflict):
        log.debug("409 Conflict — reclaiming session (normal during takeover)")
    elif isinstance(err, (NetworkError, TimedOut)):
        log.warning("Telegram network error (will retry): %s", err)
        # Bump the update time on network errors — we know polling is trying
        global _last_update_time
        _last_update_time = time.time()
    else:
        log.error("Update error: %s", err, exc_info=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def _cleanup():
    global _lock_fd
    log.info("Cleaning up resources...")
    _save_history()
    _claude_executor.shutdown(wait=True, cancel_futures=True)
    try:
        if _lock_fd and not _lock_fd.closed:
            _lock_fd.close()
    except Exception:
        pass
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


_app_ref = None


def _signal_handler(signum, frame):
    """Handle SIGTERM/SIGINT — stop the app gracefully."""
    sig_name = signal.Signals(signum).name
    log.info("Received %s, shutting down...", sig_name)
    _save_history()
    if _app_ref:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.call_soon_threadsafe(_app_ref.stop)
        except Exception:
            pass
    sys.exit(0)


def main():
    global _app_ref

    if not BOT_TOKEN:
        log.error("DASHA_BOT_TOKEN not set in .env")
        sys.exit(1)

    if not Path(CLAUDE_PATH).exists():
        log.error("Claude CLI not found at %s", CLAUDE_PATH)
        sys.exit(1)

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    atexit.register(_cleanup)

    # Kill any competing instances of this script before acquiring lock
    my_pid = os.getpid()
    competitor_pids: set[int] = set()
    try:
        # Method 1: pgrep by full path (works when launched from terminal)
        r1 = subprocess.run(["pgrep", "-f", "dasha-bot/bot.py"], capture_output=True, text=True)
        for p in r1.stdout.strip().split("\n"):
            if p.strip():
                competitor_pids.add(int(p.strip()))

        # Method 2: PID file (works when launched by LaunchAgent as "Python bot.py")
        pid_file = Path.home() / "logs" / "dasha-bot.pid"
        if pid_file.exists():
            try:
                saved_pid = int(pid_file.read_text().strip())
                if saved_pid and saved_pid != my_pid:
                    competitor_pids.add(saved_pid)
            except (ValueError, OSError):
                pass

        competitor_pids.discard(my_pid)
        for competitor in competitor_pids:
            try:
                log.info("Evicting competing instance PID %d", competitor)
                os.kill(competitor, signal.SIGTERM)
            except ProcessLookupError:
                pass
        if competitor_pids:
            time.sleep(2)  # wait for them to die
    except Exception as e:
        log.warning("Could not evict competitors: %s", e)

    acquire_lock()
    write_pid()
    write_heartbeat()
    _load_history()

    log.info("Даша starting, PID %d", os.getpid())

    # --- Aggressive session takeover ---
    # Force-evict any other getUpdates session (local or remote)
    import urllib.request
    _api = f"https://api.telegram.org/bot{BOT_TOKEN}"
    log.info("Forcing session takeover — evicting competing pollers...")
    for attempt in range(10):
        try:
            req = urllib.request.Request(
                f"{_api}/getUpdates",
                data=json.dumps({"offset": -1, "timeout": 0}).encode(),
                headers={"Content-Type": "application/json"},
            )
            resp = urllib.request.urlopen(req, timeout=5)
            data = json.loads(resp.read())
            if data.get("ok"):
                log.info("Session claimed on attempt %d", attempt + 1)
                break
        except Exception as e:
            if "409" in str(e):
                log.info("Takeover attempt %d — evicted competitor, retrying...", attempt + 1)
                time.sleep(0.5)
            else:
                log.warning("Takeover attempt %d failed: %s", attempt + 1, e)
                time.sleep(1)
    else:
        log.warning("Could not fully claim session after 10 attempts, starting anyway")

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .build()
    )

    # Track ALL updates for polling health monitor (group -1 = runs before everything)
    app.add_handler(TypeHandler(Update, _track_update), group=-1)

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("agents", cmd_agents))
    app.add_handler(CommandHandler("agentstatus", cmd_agentstatus))
    app.add_handler(CommandHandler("recover", cmd_recover))
    app.add_handler(CommandHandler("readcode", cmd_readcode))

    app.add_handler(CommandHandler("deploy", cmd_deploy))

    # Mode commands
    for mode_name in MODE_PREFIXES:
        app.add_handler(CommandHandler(mode_name, cmd_set_mode))

    # Text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Photos / screenshots
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Error handler
    app.add_error_handler(error_handler)

    # Heartbeat every 1 hour
    app.job_queue.run_repeating(heartbeat_job, interval=3600, first=10)

    # Watchdog — check every 5 min if _processing is stuck
    app.job_queue.run_repeating(watchdog_job, interval=300, first=30)

    # Polling health monitor — restart polling if dead for 15 min
    app.job_queue.run_repeating(_polling_health_job, interval=300, first=60)

    _app_ref = app

    log.info("Даша polling started")
    try:
        app.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
        )
    finally:
        _cleanup()


if __name__ == "__main__":
    main()
