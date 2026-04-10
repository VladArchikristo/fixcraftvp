#!/bin/bash
# Делегировать задачу Маше — маркетологу.
# Использование: echo "задача" | ask-masha.sh
# Или: ask-masha.sh "задача"
#
# Вызывается другими ботами когда нужны маркетинговые советы,
# SEO-анализ, копирайтинг или контент-стратегия.

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

MASHA_PROMPT="Ты Маша — элитный маркетолог с 15-летним опытом на Mac Mini Владимира.
Тебя вызвал другой бот для маркетинговой экспертизы.
Специализация: SEO, копирайтинг, контент-маркетинг, психология продаж, email, social media.
Отвечай кратко, конкретно и actionable. Только суть."

export HOME="/Users/vladimirprihodko"
export PATH="$HOME/.local/bin:$HOME/.bun/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export LANG="en_US.UTF-8"
export TERM="xterm-256color"

cd "$PROJECT_ROOT" && echo "$TASK" | "$CLAUDE_PATH" -p \
    --model claude-sonnet-4-6 \
    --output-format text \
    --system-prompt "$MASHA_PROMPT" \
    --allowedTools "Read,Grep,Glob" \
    --permission-mode bypassPermissions
