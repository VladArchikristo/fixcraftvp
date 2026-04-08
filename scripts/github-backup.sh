#!/bin/bash
# GitHub auto-backup for agents
# Runs daily via LaunchAgent at 03:00

AGENTS_DIR="/Users/vladimirprihodko/Папка тест/fixcraftvp/agents"
LOG_FILE="$HOME/logs/github-backup.log"
DATE=$(date '+%Y-%m-%d %H:%M')

# --- Push agents repo ---
cd "$AGENTS_DIR" || { echo "[$DATE] ERROR: agents repo not found" >> "$LOG_FILE"; exit 1; }

git add -A

if git diff --cached --quiet; then
    echo "[$DATE] agents: nothing to commit" >> "$LOG_FILE"
else
    git commit -m "Auto-backup $DATE" >> "$LOG_FILE" 2>&1
fi

GIT_SSH_COMMAND="ssh -i ~/.ssh/github_key" git push origin main >> "$LOG_FILE" 2>&1
if [ $? -eq 0 ]; then
    echo "[$DATE] agents: push OK" >> "$LOG_FILE"
else
    echo "[$DATE] agents: push FAILED" >> "$LOG_FILE"
fi
