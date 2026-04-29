#!/usr/bin/env python3
"""
Symphony Conductor — автономный диспетчер задач.
Читает pending задачи из task_queue → запускает агентов → отчитывается.

Запускается как daemon через LaunchAgent com.vladimir.conductor.
Цикл: каждые 60 секунд.
"""
import os
import sys
import json
import time
import logging
import subprocess
import threading
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Suppress SSL warnings
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, '/Users/vladimirprihodko/Папка тест/fixcraftvp/shared-memory')
from shared_memory import get_pending_tasks, update_task_status, get_running_tasks_count

LOG_FILE = os.path.expanduser("~/logs/conductor.log")
PID_FILE = os.path.expanduser("~/logs/conductor.pid")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

PROJECT_ROOT = '/Users/vladimirprihodko/Папка тест/fixcraftvp'
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, 'scripts')
REPO_NAME = "VladArchikristo/agents"
OWNER_CHAT_ID = 244710532
MAX_PARALLEL = 3
LOOP_INTERVAL = 60  # секунды

BOT_SCRIPTS = {
    "kostya":  "ask-kostya.sh",
    "masha":   "ask-masha.sh",
    "vasily":  "ask-vasily.sh",
    "philip":  "ask-philip.sh",
    "zina":    "ask-zina.sh",
    "peter":   "ask-peter.sh",
    "alexey":  "ask-alexey.sh",
    "beast":   "ask-beast.sh",
    "nexus":   None,  # Claude Code CLI напрямую
}

_active_tasks = set()
_lock = threading.Lock()


def load_env():
    env = {}
    for env_path in [
        os.path.join(PROJECT_ROOT, '.env'),
        os.path.join(PROJECT_ROOT, 'beast-bot', '.env'),
    ]:
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        k, v = line.split('=', 1)
                        env.setdefault(k.strip(), v.strip())
    return env


ENV = {}


def send_telegram(text: str):
    """Отправляет уведомление Владу через Beast bot."""
    token = ENV.get("BEAST_BOT_TOKEN")
    if not token:
        log.warning("BEAST_BOT_TOKEN not found, cannot send Telegram")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": OWNER_CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=10
        )
    except Exception as e:
        log.warning(f"Telegram send failed: {e}")


def post_github_comment(issue_number: int, body: str):
    """Постит комментарий к Issue на GitHub."""
    token = ENV.get("GITHUB_TOKEN")
    if not token:
        return
    try:
        from github import Github
        g = Github(token)
        repo = g.get_repo(REPO_NAME)
        issue = repo.get_issue(issue_number)
        issue.create_comment(body)
        issue.edit(state="closed")
        # Убираем лейбл in_progress
        try:
            issue.remove_from_labels("in_progress")
        except Exception:
            pass
        try:
            repo.get_label("done")
        except Exception:
            repo.create_label("done", "0e8a16")
        issue.add_to_labels("done")
    except Exception as e:
        log.warning(f"GitHub comment failed for #{issue_number}: {e}")


def run_task(task: dict):
    """Выполняет задачу и отчитывается. Запускается в отдельном потоке."""
    github_id = task["github_id"]
    title = task["title"]
    body = task["body"] or ""
    label = task["label"] or "philip"
    script = BOT_SCRIPTS.get(label)

    log.info(f"Starting task #{github_id} '{title}' → {label}")
    update_task_status(github_id, "running")

    agent_name = label.capitalize()
    task_prompt = f"Задача из GitHub Issue #{github_id}:\n\n**{title}**\n\n{body}\n\nВыполни задачу и отпиши результат."

    try:
        if script is None:
            # nexus — Claude Code CLI напрямую
            result = run_claude_direct(task_prompt, github_id)
        else:
            script_path = os.path.join(SCRIPTS_DIR, script)
            result = run_bot_script(script_path, task_prompt)

        # Обрезаем результат для GitHub (max 2000 chars)
        result_short = result[:2000] + ("…" if len(result) > 2000 else "")

        update_task_status(github_id, "done", result)

        # GitHub comment
        comment = f"✅ Выполнено агентом: {agent_name}\n\n{result_short}\n\n—Nexus, {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        post_github_comment(github_id, comment)

        # Telegram
        tg_msg = f"✅ Задача #{github_id} выполнена\n*{title}*\nИсполнитель: {agent_name}"
        send_telegram(tg_msg)
        log.info(f"Task #{github_id} done")

    except Exception as e:
        error_msg = str(e)
        update_task_status(github_id, "failed", error_msg)
        post_github_comment(github_id, f"❌ Ошибка агента {agent_name}:\n```\n{error_msg[:1000]}\n```")
        send_telegram(f"❌ Задача #{github_id} провалилась\n*{title}*\nОшибка: {error_msg[:200]}")
        log.error(f"Task #{github_id} failed: {e}")

    finally:
        with _lock:
            _active_tasks.discard(github_id)


def run_bot_script(script_path: str, task: str) -> str:
    """Запускает ask-*.sh скрипт и возвращает вывод."""
    env = os.environ.copy()
    env["HOME"] = "/Users/vladimirprihodko"
    env["PATH"] = f"{env['HOME']}/.local/bin:{env['HOME']}/.bun/bin:/usr/local/bin:/usr/bin:/bin"
    env["LANG"] = "en_US.UTF-8"

    proc = subprocess.run(
        ["/bin/bash", script_path, task],
        capture_output=True,
        text=True,
        timeout=3600,
        env=env,
        cwd=PROJECT_ROOT
    )
    output = proc.stdout.strip()
    if proc.returncode != 0 and not output:
        raise RuntimeError(proc.stderr[:500] or f"exit code {proc.returncode}")
    return output or "(нет вывода)"


def run_claude_direct(task: str, github_id: int) -> str:
    """Запускает Claude Code CLI для nexus-задач."""
    claude_path = "/Users/vladimirprihodko/.local/bin/claude"
    system = (
        "Ты Nexus — Claude Code на Mac Mini Владимира. "
        f"Выполни задачу из GitHub Issue #{github_id}. "
        "Проект: /Users/vladimirprihodko/Папка тест/fixcraftvp. "
        "После выполнения напиши краткий отчёт о том, что сделал."
    )
    env = os.environ.copy()
    env["HOME"] = "/Users/vladimirprihodko"
    env["PATH"] = f"{env['HOME']}/.local/bin:{env['HOME']}/.bun/bin:/usr/local/bin:/usr/bin:/bin"

    proc = subprocess.run(
        [claude_path, "-p", task,
         "--model", "claude-sonnet-4-6",
         "--output-format", "text",
         "--system-prompt", system,
         "--allowedTools", "Read,Edit,Write,Grep,Glob,Bash",
         "--permission-mode", "bypassPermissions"],
        capture_output=True,
        text=True,
        timeout=3600,
        env=env,
        cwd=PROJECT_ROOT
    )
    return proc.stdout.strip() or "(нет вывода)"


def main_loop():
    """Главный цикл Conductor'а."""
    global ENV
    ENV = load_env()
    log.info("Conductor started")
    send_telegram("🎼 Symphony Conductor запущен. Жду задач из GitHub Issues.")

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as executor:
        while True:
            try:
                tasks = get_pending_tasks()
                with _lock:
                    active_count = len(_active_tasks)

                for task in tasks:
                    github_id = task["github_id"]
                    if github_id is None:
                        continue

                    with _lock:
                        if github_id in _active_tasks:
                            continue
                        if len(_active_tasks) >= MAX_PARALLEL:
                            break
                        _active_tasks.add(github_id)

                    executor.submit(run_task, task)

            except Exception as e:
                log.error(f"Loop error: {e}")

            time.sleep(LOOP_INTERVAL)


if __name__ == "__main__":
    # Записываем PID
    os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    main_loop()
