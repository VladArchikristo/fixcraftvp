---
name: project-save
description: Сохраняет все материалы по проекту на диск в единую папку. Триггеры: "сохрани на диск", "сохрани всё по проекту", "собери материалы по [проект]", "создай папку проекта", "/project-save", "save project materials", "архивируй проект". Используй когда Влад просит сохранить всё связанное с конкретным проектом в одно место.
---

# Project Save

Собирает все материалы по проекту в единую папку на диске и делает git-save.

## Аргументы

`/project-save [название]` — название проекта (например: fixcraft, haulwallet, zina, trading)

Если название не указано — спроси или определи из контекста текущего разговора.

## Процедура

### 1. Определить проект

- Из аргументов: `/project-save fixcraft`
- Из контекста разговора: "сохрани всё по FixCraft" → проект = fixcraft
- Если непонятно — спроси одним вопросом

### 2. Найти папку проекта

Проверь существует ли папка `/Users/vladimirprihodko/Папка тест/fixcraftvp/<project>/`:
- Если есть — используй её
- Если нет — создай: `mkdir -p <project-folder>`

**Стандартные папки проектов:**
- `fixcraft` → `fixcraftvp/fixcraft/`
- `haulwallet` → `fixcraftvp/toll-navigator/` (или создай `haulwallet/`)
- `trading` → `fixcraftvp/trading-bot/`
- `zina` → `fixcraftvp/zina-bot/`
- Новый проект → создай папку с названием

### 3. Собрать материалы

Ищи по всему репо файлы связанные с проектом:

```bash
# Ищем по ключевым словам названия проекта
find /Users/vladimirprihodko/Папка\ тест/fixcraftvp -name "*<project>*" \
  -not -path "*/node_modules/*" \
  -not -path "*/.next/*" \
  -not -path "*/.git/*"
```

**Источники материалов:**
- `masha-bot/` — SEO статьи, маркетинг, контент, дайджесты
- `coder-bot/` — код, отчёты, документация
- `seo-articles/` — SEO контент
- `seo-content/` — тексты
- `marketing-assets/` — маркетинг
- `marketing/` — маркетинговые материалы
- `logos/` — логотипы и бренд
- `shared/` и `shared-memory/` — общие данные
- `*.md` файлы в корне репо по теме проекта

**Структура папки проекта:**
```
<project>/
  site/          ← код сайта (Next.js или другое)
  seo/           ← SEO материалы
  marketing/     ← маркетинг
  logos/         ← логотипы
  docs/          ← документация, отчёты, планы
  ai-agent/      ← backend/API если есть
```

### 4. Уведомить ботов

Если Philip запущен (проверь через PID файл `~/logs/philip-bot.pid`):

```bash
PHILIP_TOKEN=$(grep PHILIP_BOT_TOKEN /Users/vladimirprihodko/Папка\ тест/fixcraftvp/philip-bot/.env | cut -d= -f2)
VLAD_ID="244710532"

# Маше
curl -s -X POST "https://api.telegram.org/bot${PHILIP_TOKEN}/sendMessage" \
  -d chat_id="${VLAD_ID}" \
  -d text="/m Маша, сохрани все свои материалы по проекту <project> в папку <project-folder>/. Документы, SEO, маркетинг — всё туда."

# Косте
curl -s -X POST "https://api.telegram.org/bot${PHILIP_TOKEN}/sendMessage" \
  -d chat_id="${VLAD_ID}" \
  -d text="/k Костя, сохрани все материалы и код по проекту <project> в папку <project-folder>/."
```

### 5. Git Save

После сборки запусти git-save:

```bash
cd /Users/vladimirprihodko/Папка\ тест/fixcraftvp
git add <project-folder>/
git commit -m "chore: save all <project> materials to <project>/ folder"
git push
```

## Output

```
=== PROJECT SAVED ===
Project: <name>
Folder: fixcraftvp/<name>/
Files copied: N
Bots notified: Маша ✓, Костя ✓
Git pushed: main ✓
```

## Правила

- Не трогай `.env`, токены и пароли — не копируй их в папку проекта
- Не копируй `node_modules/`, `.next/`, `.git/`
- Если файл уже в нужном месте — не дублируй, просто подтверди
- Всегда делай git-save в конце
