#!/bin/bash
# Делегировать задачу Зине — астрологу и нумерологу.
# Использование: echo "вопрос" | ask-zina.sh
# Или: ask-zina.sh "вопрос"

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

ZINA_PROMPT="Ты — Зина, мудрый агент в области астрологии, нумерологии и эзотерики.
Тебя вызвал другой бот для получения астрологической или нумерологической консультации.
Отвечай с достоинством и глубиной, опираясь на символику чисел и планет.
Будь конкретен — это межботовый запрос, не диалог с пользователем."

export HOME="/Users/vladimirprihodko"
export PATH="$HOME/.local/bin:$HOME/.bun/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export LANG="en_US.UTF-8"
export TERM="xterm-256color"

cd "$PROJECT_ROOT" && echo "$TASK" | "$CLAUDE_PATH" -p \
    --model claude-sonnet-4-6 \
    --output-format text \
    --system-prompt "$ZINA_PROMPT" \
    --allowedTools "" \
    --permission-mode bypassPermissions
