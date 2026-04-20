---
date: 2026-04-20
type: hot
---

## Последняя сессия
- Heartbeat-мониторинг весь день: все системы OK, trading bot генерирует quick logs
- Git auto-save коммит 1089e2b (11:09), новые quick logs накопились (11:14–11:56)
- Session cache обновлялся дважды после обнаружения устаревания

## Активные проекты
- **Trading Bot (Василий)** — работает, quick logs каждые 5 мин, paper portfolio активен
- **Telegram Bots** — все боты с трёхуровневой memory system (L1/L2/L3), Philip восстановлен
- **Shared Memory** — 63 факта извлечены, Haiku extraction интегрирован во все боты
- **Site (FixCraft)** — CSRF origin validation задеплоен (3ebb7c4)
- **Костя** — фикс тикера (continue вместо break) работает, PID через LaunchAgent

## Незавершённое
- git-save: submodule changes + trading quick logs + news_signal не запушены
- Костя: механизм прерывания стриминга (стоп-команда) — не реализован
- Хук перед задачами (с 17 апр) — pending
- FixCraft TMA — не начата
- Google Play Developer регистрация — ручная через VNC
- Дубликат shared_memory.db в корне — нужен cleanup

## Важные правила
- **git-save = только GitHub**, Vercel только для site-source деплоя
- **НЕ редактировать** beast-bot/bot.py, .env, launcher.sh, LaunchAgent plist
- Проверка ботов только через PID файлы (`~/logs/<bot>.pid`)
- Экономия токенов: Haiku для не-срочных поисков, сжимай контекст
