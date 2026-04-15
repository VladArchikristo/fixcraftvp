#!/bin/bash
# Делегировать задачу Доктору Петру — медицинскому агенту.
# Использование: echo "вопрос" | ask-peter.sh
# Или: ask-peter.sh "вопрос"

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

PETER_PROMPT="Ты — Доктор Пётр, серьёзный медицинский агент с глубокими знаниями в области биологии, анатомии, физиологии и клинической медицины.
Тебя вызвал другой бот для получения медицинской консультации или информации.
Отвечай точно, аргументированно, с опорой на доказательную базу.
Будь краток и конкретен — это межботовый запрос, не диалог с пользователем."

export HOME="/Users/vladimirprihodko"
export PATH="$HOME/.local/bin:$HOME/.bun/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export LANG="en_US.UTF-8"
export TERM="xterm-256color"

cd "$PROJECT_ROOT" && echo "$TASK" | "$CLAUDE_PATH" -p \
    --model claude-sonnet-4-6 \
    --output-format text \
    --system-prompt "$PETER_PROMPT" \
    --allowedTools "" \
    --permission-mode bypassPermissions
