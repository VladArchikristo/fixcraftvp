# Symphony Upgrade — Nexus Architecture Plan
*Дата: 2026-04-28 | Статус: DRAFT*

---

## Что строим

Превращаем текущую схему (Влад → Telegram → Beast → Nexus → боты) в автономный контур:

```
GitHub Issues → Conductor (новый) → Philip → ask-*.sh → Костя/Маша/Вася/...
                     ↓                                           ↓
               SQLite task_queue                     GitHub comment + PR
                     ↓
               Telegram уведомление Владу
```

**Без Symphony:** Влад сам открывает сессии, дает задачи, проверяет результат.  
**С Symphony:** Влад создает Issue → система сама работает → Влад получает результат.

---

## Текущий стек (что есть)

| Компонент | Файл | Статус |
|---|---|---|
| Philip orchestrator | `philip-bot/bot.py` | ✅ работает, dispatch через bash |
| Shared memory | `shared-memory/memory.db` | ✅ SQLite, все боты |
| Delegation shells | `scripts/ask-*.sh` | ✅ 6 ботов |
| GitHub backup | `scripts/github-backup.sh` | ✅ SSH push, нет API |
| GitHub Issues API | — | ❌ отсутствует |
| Task queue | — | ❌ нет |
| Auto-dispatch | — | ❌ нет |
| Result reporting | — | ❌ нет |

---

## Фазы реализации

---

### Фаза 0 — Подготовка (2 часа)

**Что делаем:**
1. Создать GitHub Personal Access Token (scope: `issues`, `pull_requests`, `contents`)
2. Добавить `GITHUB_TOKEN` в `.env` проекта
3. Добавить `pip install PyGithub` в requirements
4. Определить репозиторий-трекер: `VladArchikristo/fixcraftvp` (уже есть)

**Соглашения по Issues:**
- Лейблы: `kostya`, `masha`, `vasily`, `nexus`, `philip` → маршрутизация
- Лейбл `agent-task` → задача для автономного выполнения
- Body формат:
  ```
  ## Task
  Описание задачи на русском или английском
  
  ## Blocked-by
  #123  (опционально)
  
  ## Context
  Дополнительный контекст (опционально)
  ```

**Проверка:** `GITHUB_TOKEN` работает, можно создать тестовый Issue через `gh issue create`.

---

### Фаза 1 — task_queue в SQLite (3 часа)

**Файл:** `shared-memory/shared_memory.py`

Добавить таблицу `tasks` в существующую `memory.db`:

```sql
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    github_id   INTEGER UNIQUE,          -- Issue number
    title       TEXT NOT NULL,
    body        TEXT,
    label       TEXT,                    -- kostya/masha/vasily/nexus/philip
    status      TEXT DEFAULT 'pending',  -- pending/running/done/failed
    blocked_by  TEXT,                    -- JSON list of issue numbers
    result      TEXT,                    -- Ответ агента
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

Функции для добавления в `shared_memory.py`:
- `add_task(github_id, title, body, label, blocked_by=None)`
- `get_pending_tasks(label=None)` → только незаблокированные
- `update_task_status(github_id, status, result=None)`
- `is_task_blocked(github_id)` → проверяет blocked_by по статусам

**Проверка:** `python3 -c "from shared_memory import add_task; add_task(1, 'test', '', 'kostya')"` не падает.

---

### Фаза 2 — GitHub Issues Watcher (4 часа)

**Файл:** `scripts/github-watcher.py` (новый)

```python
#!/usr/bin/env python3
"""
GitHub Issues → task_queue bridge.
Запускается каждые 5 минут через cron.
"""
from github import Github
import json, sys
sys.path.insert(0, '/Users/vladimirprihodko/Папка тест/fixcraftvp/shared-memory')
from shared_memory import add_task, update_task_status

REPO = "VladArchikristo/fixcraftvp"
TASK_LABEL = "agent-task"
BOT_LABELS = {"kostya", "masha", "vasily", "nexus", "philip", "zina", "peter"}
```

**Логика:**
1. Получить все Issues с лейблом `agent-task` и статусом `open`
2. Для каждого Issue:
   - Если `status != 'in_progress'` и не в `task_queue` → добавить в очередь
   - Установить лейбл `in_progress` на GitHub
   - Определить целевого бота по лейблам: `kostya` → Костя, иначе → Philip
3. Для завершённых задач (status=`done`/`failed`):
   - Закрыть Issue на GitHub
   - Добавить comment с результатом

**Cron:** каждые 5 минут:
```
*/5 * * * * /usr/bin/python3 /Users/vladimirprihodko/Папка\ тест/fixcraftvp/scripts/github-watcher.py >> ~/logs/github-watcher.log 2>&1
```

**Проверка:** создать тестовый Issue с лейблом `agent-task` + `kostya` → появляется в БД.

---

### Фаза 3 — Conductor (главный диспетчер) (5 часов)

**Файл:** `scripts/conductor.py` (новый)

Conductor — это демон, который:
1. Каждые 60 секунд читает `pending` задачи из `task_queue`
2. Проверяет `blocked_by` → пропускает если заблокировано
3. Запускает задачу через `ask-*.sh` или `claude code` напрямую
4. Пишет результат обратно в БД и на GitHub

```python
class Conductor:
    BOT_SCRIPTS = {
        "kostya":  "ask-kostya.sh",
        "masha":   "ask-masha.sh",
        "vasily":  "ask-vasily.sh",
        "nexus":   None,  # Запускается через Claude Code CLI напрямую
        "philip":  "ask-philip.sh",
        "zina":    "ask-zina.sh",
        "peter":   "ask-peter.sh",
    }
    MAX_PARALLEL = 3  # Не более 3 параллельных задач
```

**Для `nexus` задач** (архитектурные, код):
```bash
claude --model claude-sonnet-4-6 \
  --system "Ты Nexus..." \
  --allowedTools "Read,Edit,Write,Grep,Glob,Bash" \
  --dangerouslySkipPermissions \
  -p "{task_body}"
```

**Для остальных** — вызов существующих `ask-*.sh` скриптов.

**Параллельность:** `ThreadPoolExecutor(max_workers=3)` — до 3 агентов одновременно.

**Запуск:** LaunchAgent `com.vladimir.conductor` (по аналогии с другими ботами).

**Проверка:** создать 2 тестовых Issue → оба выполнились параллельно, результаты в GitHub comments.

---

### Фаза 4 — Result Reporting (2 часа)

**Файл:** расширение `conductor.py`

После завершения задачи:
1. **GitHub comment** с результатом:
   ```
   ✅ Выполнено агентом: Костя
   
   {result_text[:2000]}
   
   —Nexus, {datetime}
   ```
2. **Telegram уведомление** Владу (через Beast bot API или напрямую):
   ```
   Задача #42 "Исправить баг с сортировкой" — готово ✅
   Исполнитель: Костя
   [Ссылка на Issue]
   ```
3. **Закрыть Issue** на GitHub: `issue.edit(state="closed")`
4. **Создать PR** если задача была `nexus`/`kostya` и есть изменения в коде:
   - `git checkout -b agent/issue-{number}`
   - `git add -A && git commit -m "fix: {issue_title} (closes #{number})"`
   - `gh pr create --title "..." --body "Closes #{number}"`

**Проверка:** Issue закрывается автоматически, Влад получает Telegram сообщение.

---

### Фаза 5 — Speculative Tasks & Sub-tasks (3 часа)

**Возможность создавать дочерние задачи:**

Агент может сам создать новый Issue если обнаружил связанную проблему:
```python
def create_subtask(parent_id: int, title: str, body: str, label: str):
    """Агент создаёт дочернюю задачу."""
    issue = repo.create_issue(
        title=f"[sub #{parent_id}] {title}",
        body=f"Blocked-by: #{parent_id}\n\n{body}",
        labels=["agent-task", label]
    )
```

**Спекулятивные задачи** — задачи без точного результата:
- Лейбл `speculative` → агент исследует и докладывает без коммитов в код
- Пример: "Исследуй возможность замены SQLite на Redis для shared-memory"

**Проверка:** агент создал sub-issue → conductor его подхватил и выполнил.

---

## Итоговая архитектура

```
Влад
  │
  ├─ Telegram → Beast → Nexus (как раньше, для срочного)
  │
  └─ GitHub Issue (agent-task + kostya/masha/...) 
       │
       ▼
  github-watcher.py (cron 5min)
       │ INSERT INTO tasks
       ▼
  conductor.py (daemon, 60s loop)
       │ MAX 3 параллельных
       ├─ ask-kostya.sh → Костя → Git commit → PR
       ├─ ask-masha.sh  → Маша  → GitHub comment
       ├─ claude CLI    → Nexus → Edit files → PR
       └─ ask-vasily.sh → Вася  → Trading report
            │
            ▼
       GitHub comment + Telegram → Влад
```

---

## Оценка трудозатрат

| Фаза | Время | Сложность |
|---|---|---|
| 0 — Подготовка (токен, соглашения) | 30 мин | Низкая |
| 1 — task_queue в SQLite | 2 часа | Низкая |
| 2 — GitHub Watcher | 3 часа | Средняя |
| 3 — Conductor daemon | 5 часов | Высокая |
| 4 — Result reporting | 2 часа | Средняя |
| 5 — Sub-tasks (опционально) | 3 часа | Средняя |
| **Итого (MVP без Фазы 5)** | **~12 часов** | |

---

## Риски и ограничения

1. **GitHub rate limit:** 5000 req/hour — cron 5min = 288 req/day, ок
2. **Длинные задачи:** Claude timeout 600s — нужен Фаза 3 watchdog
3. **Конфликты веток:** если 2 агента меняют один файл → нужен lock на файл
4. **Безопасность:** GitHub token в .env, НЕ в git — обязательно добавить в .gitignore
5. **Mac Mini offline:** если машина спит — cron не сработает → нужен `caffeinate` в LaunchAgent

---

## Приоритет запуска

**MVP (начать с этого):**
1. Фаза 0 — GitHub token (30 мин)
2. Фаза 1 — task_queue (2 часа)
3. Фаза 2 — Watcher (3 часа)
4. Фаза 4 — Reporting (2 часа)
→ Итого ~7.5 часов → Влад кидает Issue → Костя выполняет → комментарий + Telegram

**Потом:** Фаза 3 (Conductor daemon + параллельность) + Фаза 5 (sub-tasks)

---

*Источник вдохновения: OpenAI Symphony (27 апреля 2026)*  
*github.com/openai/symphony*
