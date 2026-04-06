#!/bin/bash
# GitHub auto-backup for fixcraftvp bots
# Runs daily via cron

REPO_DIR="/Users/vladimirprihodko/Папка тест/fixcraftvp"
LOG_FILE="$HOME/logs/github-backup.log"
DATE=$(date '+%Y-%m-%d %H:%M')

cd "$REPO_DIR" || exit 1

# Stage all changes (respects .gitignore)
git add -A

# Check if there's anything to commit
if git diff --cached --quiet; then
    echo "[$DATE] No changes to backup" >> "$LOG_FILE"
    exit 0
fi

# Commit with date
git commit -m "Auto-backup $DATE"

# Push via SSH key
GIT_SSH_COMMAND="ssh -i ~/.ssh/github_key" git push origin main >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    echo "[$DATE] Backup OK" >> "$LOG_FILE"
else
    echo "[$DATE] Backup FAILED" >> "$LOG_FILE"
fi
