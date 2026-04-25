---
date: 2026-04-24
type: hot
---

## Последняя сессия
- Cron автосейвы восстановлены — haiku-runner.sh работает, коммиты 3ede704 и 3f10a5e прошли автоматически
- Trading bot перешёл в STOP_NEW_ENTRIES — позиции закрыты, портфель cash (+1.9%)
- Алексей (@usa_lawyer_bot) задеплоен с vision, файлы НЕ закоммичены

## Активные проекты
- **Trading Bot (Василий)** — STOP_NEW_ENTRIES, cash (+1.9%), данные обновляются
- **Алексей** (@usa_lawyer_bot) — задеплоен, vision, файлы не в git
- **Philip Bot** — Google Calendar API pending (включить в Cloud Console)
- **Костя** — фикс тикера применён, механизм прерывания стриминга не реализован
- **Зина** — семейная память работает, стабильна
- **Beast Bot** — фронтенд v10, работает
- **Shared Memory** — 63+ фактов, AI extraction через Haiku
- **Toll Navigator** — парсинг 5000 дорог завершён, деплой pending
- **FixCraftVP GBP** — одобрен, активен

## Незавершённое
- **Git-save** — submodule changes, trading data, Toll Navigator незакоммичены
- Philip: Google Calendar API — включить в Google Cloud Console
- Костя: механизм прерывания стриминга
- Toll Navigator: деплой pending
- FixCraft TMA — не начата
- Google Play Developer регистрация — ручная через VNC
- Asylum case: Congressional Inquiry, документы из России

## Важные правила
- **git-save = только GitHub**, Vercel только для site-source деплоя
- **НЕ редактировать** beast-bot/bot.py, .env, launcher.sh, LaunchAgent plist
- **Проверка ботов** — только через PID файлы в ~/logs/, НЕ через ps aux | grep
- **Экономия токенов** — Haiku для поиска, сжимать контекст
