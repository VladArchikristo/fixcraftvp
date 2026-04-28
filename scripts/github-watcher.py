#!/usr/bin/env python3
"""
GitHub Issues → task_queue bridge.
Запускается каждые 5 минут через cron.

Лейблы для маршрутизации: kostya, masha, vasily, nexus, philip, zina, peter, alexey
Лейбл-триггер: agent-task
"""
import os
import sys
import json
import logging
from datetime import datetime

# Suppress SSL warnings
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, '/Users/vladimirprihodko/Папка тест/fixcraftvp/shared-memory')
from shared_memory import add_task, update_task_status, get_pending_tasks

LOG_FILE = os.path.expanduser("~/logs/github-watcher.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)


def load_env():
    env_path = '/Users/vladimirprihodko/Папка тест/fixcraftvp/.env'
    env = {}
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.strip()
    return env


REPO_NAME = "VladArchikristo/agents"
TASK_LABEL = "agent-task"
BOT_LABELS = {"kostya", "masha", "vasily", "nexus", "philip", "zina", "peter", "alexey", "beast"}


def parse_blocked_by(body: str) -> list:
    """Извлекает blocked-by issue numbers из тела задачи."""
    import re
    blocked = []
    if not body:
        return blocked
    match = re.search(r'##\s*Blocked-by\s*\n(.*?)(?:\n##|\Z)', body, re.DOTALL)
    if match:
        refs = re.findall(r'#(\d+)', match.group(1))
        blocked = [int(r) for r in refs]
    return blocked


def get_bot_label(issue_labels) -> str:
    """Определяет целевого бота по лейблам."""
    label_names = {lbl.name.lower() for lbl in issue_labels}
    for bot in BOT_LABELS:
        if bot in label_names:
            return bot
    return "philip"  # дефолт — оркестратор


def main():
    env = load_env()
    token = env.get("GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        log.error("GITHUB_TOKEN not found")
        sys.exit(1)

    from github import Github
    g = Github(token)

    try:
        repo = g.get_repo(REPO_NAME)
    except Exception as e:
        log.error(f"Cannot access repo {REPO_NAME}: {e}")
        sys.exit(1)

    # Получаем все open issues с лейблом agent-task
    try:
        issues = list(repo.get_issues(state="open", labels=[TASK_LABEL]))
    except Exception as e:
        log.error(f"Cannot fetch issues: {e}")
        sys.exit(1)

    added = 0
    for issue in issues:
        label_names = {lbl.name.lower() for lbl in issue.labels}

        # Пропускаем если уже в работе
        if "in_progress" in label_names or "done" in label_names:
            continue

        bot_label = get_bot_label(issue.labels)
        blocked_by = parse_blocked_by(issue.body or "")

        # Добавляем в очередь (INSERT OR IGNORE — безопасно)
        add_task(
            github_id=issue.number,
            title=issue.title,
            body=issue.body or "",
            label=bot_label,
            blocked_by=blocked_by if blocked_by else None
        )

        # Ставим лейбл in_progress на GitHub
        try:
            # Создаём лейбл если нет
            try:
                repo.get_label("in_progress")
            except Exception:
                repo.create_label("in_progress", "fbca04")

            issue.add_to_labels("in_progress")
            log.info(f"Issue #{issue.number} '{issue.title}' → {bot_label} (queued)")
            added += 1
        except Exception as e:
            log.warning(f"Cannot add label to #{issue.number}: {e}")

    # Закрываем done/failed задачи на GitHub
    pending = get_pending_tasks()
    done_ids = set()
    for task in pending:
        if task["status"] in ("done", "failed"):
            done_ids.add(task["github_id"])

    for issue in issues:
        if issue.number in done_ids:
            try:
                issue.edit(state="closed")
                log.info(f"Issue #{issue.number} closed (task done)")
            except Exception as e:
                log.warning(f"Cannot close #{issue.number}: {e}")

    log.info(f"Watcher run complete: {added} new tasks queued, {len(issues)} issues checked")


if __name__ == "__main__":
    main()
