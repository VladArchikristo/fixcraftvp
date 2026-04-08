#!/bin/bash
# GitHub auto-backup — runs at 3am daily
# Commits all changes and pushes to origin/main

REPO="$HOME/Папка тест/fixcraftvp"
LOG="$HOME/logs/cron/github-backup.log"
DATE=$(date '+%Y-%m-%d %H:%M')

cd "$REPO" || { echo "[$DATE] ERROR: repo not found" >> "$LOG"; exit 1; }

# Check if there's anything to commit
if git diff --quiet && git diff --staged --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
    echo "[$DATE] Nothing to commit, pushing existing commits..." >> "$LOG"
else
    git add -A
    git commit -m "Auto-backup $DATE" >> "$LOG" 2>&1
fi

# Push to GitHub
git push origin main >> "$LOG" 2>&1
if [ $? -eq 0 ]; then
    echo "[$DATE] Push OK" >> "$LOG"
else
    echo "[$DATE] Push FAILED" >> "$LOG"
    exit 1
fi
