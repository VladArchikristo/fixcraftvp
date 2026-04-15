#!/bin/bash
# Делегировать задачу Косте — программисту-архитектору.
# Использование: echo "задача" | ask-kostya.sh
# Или: ask-kostya.sh "задача"
#
# Вызывается другими ботами когда нужна помощь с кодом.

CLAUDE_PATH="/Users/vladimirprihodko/.local/bin/claude"
PROJECT_ROOT="/Users/vladimirprihodko/Папка тест/fixcraftvp"

if [ -n "$1" ]; then
    TASK="$*"
else
    TASK=$(cat -)
fi

if [ -z "$TASK" ]; then
    echo "Ошибка: задача не передана" >&2
    exit 1
fi

KOSTYA_PROMPT="Ты Костя — программист-архитектор на Mac Mini Владимира.
Тебя вызвал другой бот для помощи с кодом или технической задачей.
Проект: $PROJECT_ROOT
Инструменты: Read, Edit, Write, Grep, Glob, Bash — используй их свободно.
НЕЛЬЗЯ трогать: beast-bot/bot.py, .env файлы, launcher.sh скрипты.
Отвечай кратко и по делу. Если сделал изменения — опиши что именно."

export HOME="/Users/vladimirprihodko"
export PATH="$HOME/.local/bin:$HOME/.bun/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export LANG="en_US.UTF-8"
export TERM="xterm-256color"

cd "$PROJECT_ROOT" && echo "$TASK" | "$CLAUDE_PATH" -p \
    --model claude-opus-4-6 \
    --output-format text \
    --system-prompt "$KOSTYA_PROMPT" \
    --allowedTools "Read,Edit,Write,Grep,Glob,Bash" \
    --permission-mode bypassPermissions
