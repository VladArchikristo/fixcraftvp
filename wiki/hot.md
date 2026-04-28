---
date: 2026-04-28
type: hot
---

## Последняя сессия (28 апреля, 10:56 EDT)

- **HaulWallet v13 Audit Complete** ✅ — 20 экранов аудированы, оценка 7.5/10, готово к финальной полировке
- **Philip orchestration** — Делегация задач Косте через ask-kostya.sh, результаты в HAULWALLET_V13_REPORT.md
- **Symphony MVP** — Conductor fixed, github-watcher active, github-issue #2 обработан автономно

## Последняя сессия (15 апреля)

- **Heartbeat-only циклы** — активных задач не было, только автоматические проверки каждые ~15 мин
- **Все боты живые:** Василий, Маша, Костя, Philip, Peter, Зина, Beast
- **Утром исправлены скрипты делегации** — убран несуществующий флаг `--cwd` из всех ask-*.sh

## Активные проекты

- **Toll Navigator** — IFTA + PDF shipped, деплой на Hetzner pending с 13 апреля | Высокий
- **Trading Bot (Василий)** — ETH LONG / XRP LONG, paper portfolio, daily analysis | Активный
- **Philip-bot** — оркестратор с /k /m /v /p /z /б делегацией | Стабильный
- **Зина-бот** — астро/нумерология, Vedic | Работает
- **Beast v10** — резервный агент через Philip /б | Низкий
- **Сайт FixCraft** — site-source, Vercel | По запросу

## Незавершённое

- **Деплой Toll Navigator на Hetzner** — скрипт готов, нужен VPS + JWT_SECRET (с 13 апреля!)
- **3+ auto-save коммита** не запушены на GitHub — нужен git push
- **Philip `/б` команда** — работает, но не закоммичена — нужен git-save
- **Wiki compiler** — исправлен с валидацией и rollback, мониторить качество
- **Document Scanner Phase 2** — OCR через ML Kit

## Важные правила

- **git-save = только GitHub.** НЕ включать site-source в коммит. Vercel — только для явного деплоя сайта
- **Проверка ботов — через PID файлы** (`cat ~/logs/<bot>.pid` → `ps -p <PID>`), НЕ через `ps aux | grep`
- **НЕ редактировать** beast-bot/bot.py, .env, launcher.sh, LaunchAgent plist
- **Контекст сбрасывается на 20 сообщениях** — сохранять прогресс в память до лимита
