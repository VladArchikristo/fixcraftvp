#!/bin/bash
# Делегировать задачу Василию — трейдеру и финансовому аналитику.
# Использование: echo "задача" | ask-vasily.sh
# Или: ask-vasily.sh "задача"
#
# Вызывается другими ботами когда нужен анализ рынков,
# крипто/акции, инвестиционные советы, трейдинговые стратегии.

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

VASILY_PROMPT="Ты Василий — опытный трейдер и финансовый аналитик на Mac Mini Владимира.
Тебя вызвал другой бот для финансовой экспертизы.
Специализация: криптовалюты, акции, инвестиции, рыночный анализ, торговые стратегии.
Говори уверенно, по делу, без воды. Только суть."

export HOME="/Users/vladimirprihodko"
export PATH="$HOME/.local/bin:$HOME/.bun/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export LANG="en_US.UTF-8"
export TERM="xterm-256color"

echo "$TASK" | "$CLAUDE_PATH" -p \
    --model claude-opus-4-6 \
    --output-format text \
    --system-prompt "$VASILY_PROMPT" \
    --allowedTools "Read,Grep,Glob" \
    --permission-mode bypassPermissions \
    --cwd "$PROJECT_ROOT"
