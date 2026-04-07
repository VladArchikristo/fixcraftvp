#!/bin/bash
# Делегировать задачу Мыслителю Филипу — промт-инженеру.
# Использование: echo "задача" | ask-philip.sh
# Или: ask-philip.sh "задача"
#
# Вызывается другими ботами когда нужно:
# - улучшить промт
# - создать промт из описания или тезисов
# - сделать промт для разработки приложения

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

PHILIP_PROMPT="Ты — Мыслитель Филип, мастер промт-инженерии на Mac Mini Владимира.
Тебя вызвал другой бот для помощи с промтом.
Проект: $PROJECT_ROOT
Твоя задача: улучшить, создать или переработать промт по запросу.
Техники: Chain-of-Thought, Few-Shot, Role Prompting, Tree-of-Thought, ReAct.
Если промт для разработки — сделай его production-ready, с архитектурой и структурой файлов.
Отвечай кратко: дай готовый промт в блоке кода + одно предложение объяснения."

export HOME="/Users/vladimirprihodko"
export PATH="$HOME/.local/bin:$HOME/.bun/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export LANG="en_US.UTF-8"
export TERM="xterm-256color"

echo "$TASK" | "$CLAUDE_PATH" -p \
    --model claude-sonnet-4-6 \
    --output-format text \
    --system-prompt "$PHILIP_PROMPT" \
    --allowedTools "Read,Grep,Glob" \
    --permission-mode bypassPermissions \
    --cwd "$PROJECT_ROOT"
