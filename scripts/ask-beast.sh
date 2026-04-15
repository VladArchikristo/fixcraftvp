#!/bin/bash
# Делегировать задачу Beast — общему агенту-резерву.
# Использование: echo "задача" | ask-beast.sh
# Или: ask-beast.sh "задача"
#
# Beast — самостоятельный агент, резерв на случай если другие боты недоступны.
# Работает через Claude Code CLI напрямую, не зависит от других ботов.

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

BEAST_PROMPT="Ты Beast — универсальный агент-резерв на Mac Mini Владимира.
Ты самостоятельный, независимый агент. Тебя вызвали когда другие боты недоступны или нужен общий помощник.
Проект: $PROJECT_ROOT
Инструменты: Read, Edit, Write, Grep, Glob, Bash — используй их свободно.
НЕЛЬЗЯ трогать: beast-bot/bot.py, .env файлы, launcher.sh скрипты.
Отвечай кратко и по делу на русском языке."

export HOME="/Users/vladimirprihodko"
export PATH="$HOME/.local/bin:$HOME/.bun/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export LANG="en_US.UTF-8"
export TERM="xterm-256color"

cd "$PROJECT_ROOT" || exit 1

echo "$TASK" | "$CLAUDE_PATH" -p \
    --model claude-sonnet-4-6 \
    --output-format text \
    --system-prompt "$BEAST_PROMPT" \
    --allowedTools "Read,Edit,Write,Grep,Glob,Bash" \
    --permission-mode bypassPermissions
