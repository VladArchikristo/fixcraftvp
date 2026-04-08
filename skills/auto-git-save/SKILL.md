---
name: auto-git-save
description: Автоматически сохраняет все изменения в git. Триггеры: "сохрани", "сохраняй изменения", "auto-git-save", "git save", "закоммить всё", "сохрани всё", "push изменения", после завершения сессии с изменениями файлов.
---

# Auto Git Save

Автоматически коммитит и пушит все изменения в текущем git-репозитории.

## Шаги

1. Перейди в директорию проекта: `/Users/vladimirprihodko/Папка тест/fixcraftvp`

2. Проверь что есть незакоммиченные изменения:
```bash
cd "/Users/vladimirprihodko/Папка тест/fixcraftvp" && git status --short
```

3. Если изменений нет — сообщи "Нечего сохранять, всё чисто ✓" и завершись.

4. Если есть изменения — сделай `git add` для изменённых файлов (НЕ `git add -A` чтобы не захватить случайные файлы):
```bash
git add beast-bot/ coder-bot/ trading-bot/data/ masha-bot/ agents/ site-source/
```
   Исключения (никогда не коммитить): `.env`, `*.pid`, `*.lock`, `quick_logs/`, `scan_logs/`

5. Сгенерируй сообщение коммита в формате:
   `Auto-save YYYY-MM-DD HH:MM — <краткий список изменённых компонентов>`
   
   Например: `Auto-save 2026-04-08 17:30 — beast-bot isolation, coder-bot fixes`

6. Закоммить:
```bash
git commit -m "$(cat <<'EOF'
Auto-save YYYY-MM-DD HH:MM — <компоненты>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

7. Запушить:
```bash
git push
```

8. Сообщи результат: что закоммичено, SHA коммита, статус пуша.

## Правила
- Никогда не коммитить `.env`, токены, ключи API
- Никогда не делать `git push --force`
- Если пуш упал — сообщи ошибку, не пытайся force push
