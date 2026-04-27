"""
Субагенты для ботов — параллельное выполнение маленьких задач через Claude Haiku.

Как работает:
1. Основной бот (Sonnet/Opus) отвечает и может вставить теги:
   <subagent type="research">вопрос для исследования</subagent>
   <subagent type="write">задача написать текст</subagent>
   <subagent type="analyze">что проанализировать</subagent>
   <subagent type="quick">любая быстрая задача</subagent>

2. Python код парсит эти теги и запускает все в параллельных потоках
3. Каждый суб-агент — это Claude Haiku (быстро + дёшево, ~5 сек)
4. Результаты возвращаются основному боту для финального синтеза

Использование в боте:
    from shared.subagent_utils import process_with_subagents, DELEGATION_INSTRUCTIONS
"""

from __future__ import annotations
import os
import re
import subprocess
import logging
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

log = logging.getLogger(__name__)

CLAUDE_PATH = "/Users/vladimirprihodko/.local/bin/claude"
SUBAGENT_MODEL = "claude-haiku-4-5"
SUBAGENT_TIMEOUT = 60  # секунд — быстро!
WORKING_DIR = "/Users/vladimirprihodko/Папка тест/fixcraftvp/"

# Специализированные промты для каждого типа суб-агента
SUBAGENT_SYSTEMS = {
    "research": (
        "Ты — быстрый исследователь. Отвечай кратко и по делу. "
        "Только факты, без воды. Максимум 200 слов."
    ),
    "write": (
        "Ты — профессиональный копирайтер. Пиши чётко, убедительно, кратко. "
        "Без вводных фраз, сразу результат."
    ),
    "analyze": (
        "Ты — аналитик. Выдавай структурированный анализ. "
        "Используй маркированные списки. Максимум 300 слов."
    ),
    "code": (
        "Ты — опытный разработчик. Пиши рабочий код без объяснений если не просят. "
        "Только код + краткий комментарий что делает."
    ),
    "quick": (
        "Отвечай максимально кратко и точно. Одно-два предложения или список."
    ),
    "math": (
        "Ты — математический ассистент. Считай точно, показывай шаги если нужно. "
        "Результат выдавай чётко: сначала ответ, потом расчёт."
    ),
    "format": (
        "Ты — специалист по форматированию и трансформации данных. "
        "Преобразуй, отформатируй или переведи данные в нужный формат. "
        "Только результат, без объяснений."
    ),
}

# Тег для парсинга
SUBAGENT_RE = re.compile(
    r'<subagent\s+type=["\']?(\w+)["\']?>(.*?)</subagent>',
    re.DOTALL | re.IGNORECASE,
)

# Инструкции делегирования — добавляются в system prompt каждого бота
DELEGATION_INSTRUCTIONS = """
== ОБЯЗАТЕЛЬНОЕ ПРАВИЛО: ПАРАЛЛЕЛЬНЫЕ СУБ-АГЕНТЫ ==
⚡ ВСЕГДА делегируй маленькие задачи суб-агентам. Они работают ПАРАЛЛЕЛЬНО за ~5 сек.
Это твой главный инструмент скорости. НЕ делай сам то, что может сделать суб-агент.

СИНТАКСИС — вставь теги прямо в ответ ДО того как писать финальный текст:
<subagent type="research">конкретный вопрос для поиска/исследования</subagent>
<subagent type="write">напиши [тип текста]: [тема и требования]</subagent>
<subagent type="analyze">проанализируй [что именно, по каким критериям]</subagent>
<subagent type="code">напиши код: [что делает, язык, входные данные]</subagent>
<subagent type="quick">короткий конкретный вопрос — получи быстрый ответ</subagent>
<subagent type="math">посчитай / реши задачу: [условие]</subagent>
<subagent type="format">отформатируй/переведи/преобразуй: [данные]</subagent>

КОГДА ДЕЛЕГИРОВАТЬ — делегируй ВСЕГДА если задача содержит хотя бы одно из:
✅ Нужно что-то найти, исследовать, проверить факт → research
✅ Нужно написать текст, описание, комментарий, инструкцию → write
✅ Нужно написать код, скрипт, функцию → code
✅ Нужно посчитать, сравнить варианты, оценить риски → analyze / math
✅ Несколько независимых подзадач → запусти их ВСЕ параллельно
✅ Любой вопрос который можно ответить без контекста диалога → quick

НЕ делегируй только если:
❌ Ответ требует точного контекста из текущего диалога
❌ Задача — просто сказать "да/нет" или 1 простое предложение

ЗАКОН ПАРАЛЛЕЛЬНОСТИ: несколько тегов = все запускаются ОДНОВРЕМЕННО.
3 суб-агента параллельно = всё готово за те же 5 сек, не за 15!

ПРИМЕРЫ:

Пользователь: "объясни как работает JWT"
<subagent type="research">как работает JWT токен: структура, подпись, верификация</subagent>
<subagent type="research">безопасность JWT: уязвимости и best practices 2024</subagent>

Пользователь: "напиши функцию валидации email и тест к ней"
<subagent type="code">напиши Python функцию validate_email(email: str) -> bool с regex</subagent>
<subagent type="code">напиши pytest тесты для функции validate_email: валидные и невалидные случаи</subagent>

Пользователь: "сделай план маркетинга для мобильного приложения"
<subagent type="research">лучшие ASO практики для App Store и Google Play 2024</subagent>
<subagent type="research">каналы привлечения пользователей для B2C мобильных приложений</subagent>
<subagent type="analyze">сравни платное vs органическое продвижение для мобильных приложений</subagent>
<subagent type="write">напиши шаблон описания приложения для App Store: убедительно, с ключевыми словами</subagent>
"""


def _get_claude_env() -> dict:
    """Окружение для subprocess — единая версия для всех ботов."""
    home = Path.home()
    nvm_node_bin = ""
    nvm_dir = home / ".nvm" / "versions" / "node"
    if nvm_dir.exists():
        versions = sorted(nvm_dir.iterdir(), reverse=True)
        if versions:
            nvm_node_bin = str(versions[0] / "bin")
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


def run_subagent(task: str, agent_type: str = "quick") -> str:
    """
    Запустить суб-агента (Claude Haiku) для быстрой задачи.
    Возвращает результат как строку. ~5-15 секунд.
    """
    system = SUBAGENT_SYSTEMS.get(agent_type, SUBAGENT_SYSTEMS["quick"])
    cmd = [
        CLAUDE_PATH, "-p",
        "--model", SUBAGENT_MODEL,
        "--output-format", "text",
        "--system-prompt", system,
        "--max-turns", "3",
    ]
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
        stdout, stderr = proc.communicate(input=task, timeout=SUBAGENT_TIMEOUT)
        if proc.returncode != 0:
            log.warning("Subagent [%s] failed: %s", agent_type, stderr.strip()[:200])
            return f"[Суб-агент {agent_type} не дал результата]"
        result = stdout.strip()
        log.info("Subagent [%s] done, %d chars", agent_type, len(result))
        return result or f"[Суб-агент {agent_type} — пустой ответ]"
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), 9)
        except Exception:
            pass
        return f"[Суб-агент {agent_type} — таймаут {SUBAGENT_TIMEOUT}с]"
    except Exception as e:
        log.error("Subagent [%s] error: %s", agent_type, e)
        return f"[Суб-агент {agent_type} — ошибка: {e}]"


def parse_delegates(text: str) -> list[tuple[str, str]]:
    """Найти все <subagent type="...">задача</subagent> теги."""
    return [(m.group(1), m.group(2).strip()) for m in SUBAGENT_RE.finditer(text)]


def run_parallel_delegates(delegates: list[tuple[str, str]]) -> dict[int, str]:
    """
    Запустить все суб-агенты параллельно.
    Возвращает словарь {индекс: результат}.
    """
    if not delegates:
        return {}

    results = {}
    parallel_timeout = SUBAGENT_TIMEOUT + 30  # жёсткий лимит на всю параллельную группу
    with ThreadPoolExecutor(max_workers=min(len(delegates), 5)) as pool:
        future_to_idx = {
            pool.submit(run_subagent, task, atype): i
            for i, (atype, task) in enumerate(delegates)
        }
        try:
            for future in as_completed(future_to_idx, timeout=parallel_timeout):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    results[idx] = f"[Ошибка суб-агента: {e}]"
        except concurrent.futures.TimeoutError:
            log.error("Parallel subagents timed out after %d sec — collecting partial results", parallel_timeout)
            for future, idx in future_to_idx.items():
                if idx not in results:
                    if future.done():
                        try:
                            results[idx] = future.result()
                        except Exception as e:
                            results[idx] = f"[Ошибка суб-агента: {e}]"
                    else:
                        future.cancel()
                        results[idx] = f"[Суб-агент — таймаут {parallel_timeout}с]"

    return results


def inject_subagent_results(original_response: str, delegates: list[tuple[str, str]], results: dict[int, str]) -> str:
    """
    Убрать теги из ответа, добавить результаты суб-агентов как контекст.
    """
    clean = SUBAGENT_RE.sub("", original_response).strip()

    results_block = "\n\n".join([
        f"📋 **Суб-агент [{delegates[i][0]}]** (задача: {delegates[i][1][:80]}...):\n{results[i]}"
        for i in sorted(results.keys())
        if i < len(delegates)
    ])

    if results_block:
        return f"{clean}\n\n---\n**Результаты суб-агентов:**\n{results_block}" if clean else results_block

    return clean


def two_pass_call(
    full_prompt: str,
    call_once_fn,  # callable(prompt) -> (bool, str)
    synthesis_system: str = "",
) -> tuple[bool, str]:
    """
    Двухпроходной вызов: первый проход → парсим делегаты → параллельные суб-агенты
    → второй проход с результатами → финальный ответ.

    call_once_fn должна принимать (prompt: str) и возвращать (ok: bool, text: str).
    synthesis_system — доп. инструкция для синтеза (опционально).
    """
    # Первый проход
    ok, first_response = call_once_fn(full_prompt)
    if not ok:
        return False, first_response

    # Ищем делегаты
    delegates = parse_delegates(first_response)
    if not delegates:
        return True, first_response  # Нет делегатов — возвращаем как есть

    log.info("Found %d subagent delegates, running in parallel...", len(delegates))

    # Параллельный запуск суб-агентов
    results = run_parallel_delegates(delegates)

    # Строим prompt для второго прохода
    results_lines = []
    for i, (atype, task) in enumerate(delegates):
        result = results.get(i, "[нет результата]")
        results_lines.append(f"Суб-агент [{atype}] (задача: {task[:100]}):\n{result}")

    synthesis_prompt = (
        f"{full_prompt}\n\n"
        f"---\nТвои суб-агенты выполнили задачи параллельно:\n\n"
        + "\n\n".join(results_lines)
        + "\n\n---\nТеперь дай пользователю финальный ответ используя эти данные. "
        "Не упоминай суб-агентов — просто дай исчерпывающий ответ."
    )

    # Второй проход — синтез
    ok2, final = call_once_fn(synthesis_prompt)
    if ok2:
        return True, final

    # Fallback — возвращаем первый ответ с результатами суб-агентов
    return True, inject_subagent_results(first_response, delegates, results)
