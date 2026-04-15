---
date: 2026-04-15
type: hot
---

## Последняя сессия (15 апреля)

- **Heartbeat-only циклы** — активных задач не было, автоматические проверки каждые ~15 мин
- **Все 7 ботов живые:** Василий, Маша, Костя, Philip, Peter, Зина, Beast
- **Node.js PATH фикс** — исправлена проблема с генерацией wiki hot.md в cron jobs

## Активные проекты

- **Toll Navigator** — IFTA + PDF shipped, деплой на Hetzner pending с 13 апреля | Высокий
- **Trading Bot (Василий)** — ETH LONG / XRP LONG, paper portfolio, quick_logs каждые 5 мин | Активный
- **Philip-bot** — оркестратор с /k /m /v /p /z /б делегацией | Стабильный
- **Зина-бот** — астро/нумерология, Vedic | Работает
- **Beast v10** — резервный агент через Philip /б | Низкий
- **Сайт FixCraft** — site-source, Vercel | По запросу

## Незавершённое

- **Деплой Toll Navigator на Hetzner** — скрипт готов, нужен VPS + JWT_SECRET (с 13 апреля!)
- **4 auto-save коммита не запушены на GitHub** — нужен git push
- **Philip `/б` команда** — работает, но не закоммичена — нужен git-save
- **Wiki compiler** — исправлен с валидацией и rollback, мониторить качество
- **Document Scanner Phase 2** — OCR через ML Kit

## Важные правила

- **git-save = только GitHub.** НЕ включать site-source в коммит. Vercel — только для явного деплоя сайта
- **Проверка ботов — через PID файлы** (`cat ~/logs/<bot>.pid` → `ps -p <PID>`), НЕ через `ps aux | grep`
- **НЕ редактировать** beast-bot/bot.py, .env, launcher.sh, LaunchAgent plist
- **Контекст сбрасывается на 20 сообщениях** — сохранять прогресс заранее
