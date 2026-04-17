---
date: 2026-04-17
type: hot
---

## Последняя сессия
- Починили haiku-runner.sh: 5 багов (auto-save путь, git push, monitor спам, Питер/Зина добавлены, Nexus через launchctl)
- XRP LONG закрыт +$5.75 (+3.8%), cash $1028.56, позиций нет
- HaulWallet: маркетинговые ассеты (SVG→PNG), Play Store листинг, Data Safety — всё готово к загрузке

## Активные проекты
- **Trading Bot** — paper portfolio, cash $1028, без позиций, market scan работает
- **HaulWallet** — Play Store листинг готов, PNG ассеты конвертированы, нужны OAuth ключи и Service Account
- **Toll Navigator** — парсинг 5000 дорог сделан, деплой pending
- **Боты (6 шт)** — все на shared SQLite памяти, модели: Костя=Opus, остальные=Sonnet
- **Сайт FixCraft** — деплоится через Vercel, hero видео и галерея
- **Codex CLI** — план готов, ждём OpenAI подписку $20

## Незавершённое
- ⚡ Superpowers хук: автозапуск /write-plan перед задачами (через hookify/update-config)
- HaulWallet: OAuth ключи Google/Apple, Service Account для Play Store API
- git push: coder-bot, trading-bot, peter-bot — коммиты не запушены
- Codex CLI интеграция после покупки OpenAI подписки
- Ротация quick_logs Василия (растёт без лимита)
- Алерт в Telegram при падении кронов
- Cron self-check удаление заблокировано macOS sandbox

## Важные правила
- **Полная автономия** — никогда не спрашивать подтверждений, делать до конца, субагенты для параллели
- **Экономия** — подписки > API, бесплатное > платное, всегда называть стоимость
- **git-save = только GitHub**, Vercel только для site-source деплоя
- **Статус ботов** — через PID файлы (~/logs/*.pid), НЕ через ps aux | grep имя
