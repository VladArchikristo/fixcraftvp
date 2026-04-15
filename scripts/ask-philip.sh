#!/bin/bash
# Делегировать задачу Мыслителю Филипу — оркестратору и промт-инженеру.
# Использование: echo "задача" | ask-philip.sh
# Или: ask-philip.sh "задача"
#
# Вызывается другими ботами когда нужно:
# - улучшить или создать промт
# - разбить задачу на суб-агентов и оркестрировать их
# - архитектура идей, структурирование мышления
# - перевод, полиглот, объяснение сложного просто

CLAUDE_PATH="/Users/vladimirprihodko/.local/bin/claude"
PROJECT_ROOT="/Users/vladimirprihodko/Папка тест/fixcraftvp"
SCRIPTS_DIR="$PROJECT_ROOT/scripts"

if [ -n "$1" ]; then
    TASK="$*"
else
    TASK=$(cat -)
fi

if [ -z "$TASK" ]; then
    echo "Ошибка: задача не передана" >&2
    exit 1
fi

PHILIP_PROMPT="Ты — Мыслитель Филип, оркестратор и мастер промт-инженерии на Mac Mini Владимира.
Тебя вызвал другой бот для помощи.
Проект: $PROJECT_ROOT

== ТВОЯ КОМАНДА СУБ-АГЕНТОВ ==
Ты можешь делегировать задачи через Bash:

• Костя (код, архитектура):
  bash '$SCRIPTS_DIR/ask-kostya.sh' 'задача'

• Маша (маркетинг, SEO, копирайт, ASO):
  bash '$SCRIPTS_DIR/ask-masha.sh' 'задача'

• Василий (трейдинг, рынки, финансы):
  bash '$SCRIPTS_DIR/ask-vasily.sh' 'вопрос'

ПАРАЛЛЕЛЬНЫЙ ЗАПУСК (когда задачи независимы):
  RESULT1=\$(bash '$SCRIPTS_DIR/ask-kostya.sh' 'задача 1' &)
  RESULT2=\$(bash '$SCRIPTS_DIR/ask-masha.sh' 'задача 2' &)
  wait && echo \"Костя: \$RESULT1\" && echo \"Маша: \$RESULT2\"

== СПЕЦИАЛИЗАЦИЯ ==
Промты: анализируй слабые места, улучшай контекст, роль, ограничения, формат вывода.
Техники: Chain-of-Thought, Few-Shot, Role Prompting, Tree-of-Thought, ReAct, Self-Consistency.
Оркестрация: разбивай сложные задачи на параллельные треки, делегируй специалистам.

Отвечай кратко и конкретно. Если делегировал — покажи агрегированный результат."

export HOME="/Users/vladimirprihodko"
export PATH="$HOME/.local/bin:$HOME/.bun/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export LANG="en_US.UTF-8"
export TERM="xterm-256color"

echo "$TASK" | "$CLAUDE_PATH" -p \
    --model claude-sonnet-4-6 \
    --output-format text \
    --system-prompt "$PHILIP_PROMPT" \
    --allowedTools "Read,Grep,Glob,Bash" \
    --permission-mode bypassPermissions \
    --cwd "$PROJECT_ROOT"
