#!/bin/bash
# Делегировать вопрос Алексею — адвокату США.
# Использование: echo "вопрос" | ask-alexey.sh
# Или: ask-alexey.sh "вопрос"

CLAUDE_PATH="/Users/vladimirprihodko/.local/bin/claude"
PROJECT_ROOT="/Users/vladimirprihodko/Папка тест/fixcraftvp"

if [ -n "$1" ]; then
    TASK="$*"
else
    TASK=$(cat -)
fi

if [ -z "$TASK" ]; then
    echo "Ошибка: вопрос не передан" >&2
    exit 1
fi

ALEXEY_PROMPT="Ты — Алексей, опытный американский адвокат.
Тебя вызвал другой бот для получения юридической консультации по законодательству США.
Отвечай точно, со ссылками на применимые законы и прецеденты. Будь конкретен.
Это межботовый запрос, не диалог с пользователем."

export HOME="/Users/vladimirprihodko"
export PATH="$HOME/.local/bin:$HOME/.bun/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export LANG="en_US.UTF-8"
export TERM="xterm-256color"

cd "$PROJECT_ROOT" && echo "$TASK" | "$CLAUDE_PATH" -p \
    --model claude-haiku-4-5 \
    --output-format text \
    --system-prompt "$ALEXEY_PROMPT" \
    --allowedTools "" \
    --permission-mode bypassPermissions
