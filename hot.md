---
date: 2026-04-21
type: hot
---

## Последняя сессия
- Зина: добавлена семейная память — таблица `family_members` в SQLite, команда `/family`, данные семьи Влада
- Фикс дубликатов XRP позиций в market_scan.py — проверка уникальности ассета
- Wiki документация: ~15 статей из торговых сессий конвертированы в wiki формат

## Активные проекты
- **Trading Bot (Василий)** — работает, 2x XRP LONG с $1.42, quick logs активны
- **Зина** — семейная память активна, перезапущена через nohup
- **Philip Bot** — Google Calendar интеграция завершена
- **Костя** — PID 66312, фикс тикера применён (continue вместо break)
- **Beast Bot v10** — фронтенд работает
- **Shared Memory** — 63+ факта, multi-bot архитектура
- **Toll Navigator** — парсинг 5000 дорог, деплой pending

## Незавершённое
- Git-save нужен (~55+ файлов: quick_logs, shared-memory.db, удалённые логи)
- Костя: механизм прерывания стриминга (стоп-команда) — не реализован
- Костя: фикс тикера не запушен в git
- FixCraft TMA — не начата
- Google Play Developer регистрация — ручная через VNC
- HaulWallet upload — после Google Play

## Важные правила
- **git-save = только GitHub**, Vercel только для site-source деплоя
- **НЕ редактировать** beast-bot/bot.py, .env, launcher.sh, LaunchAgent plist
- Проверка ботов через PID файлы (`~/logs/<bot>.pid`), НЕ через ps grep по имени
- Экономия токенов: Haiku для не-срочных поисков, сжимай контекст
