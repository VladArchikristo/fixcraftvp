---
date: 2026-04-28
type: hot
---

## Последняя сессия
- **Symphony MVP ЗАПУЩЕНА** — GitHub Issues → task_queue → Conductor → боты → результат в Issue + Telegram
- LaunchAgents: github-watcher (каждые 5 мин) + conductor (daemon) оба активны
- Тест: Issue #1 → Костя подхватил задачу, система работает end-to-end
- 11 GitHub лейблов созданы на VladArchikristo/agents

## Активные проекты
- **Trading Bot (Василий)** — risk-off, 100% кэш $1,018.97 (+1.9%), утренний анализ выполнен
- **FixCraftVP сайт** — 63 статьи на Vercel, 0 индексация Google, SEO recovery plan готов
- **Маша** — estimator работает, 75+ площадок для гостевых постов найдено
- **Костя** — 10 багов пофикшено, перезапущен и работает
- **Beast Bot** — фронтенд v10, стабилен
- **Алексей** (@usa_lawyer_bot) — задеплоен, НЕ закоммичен
- **Зина** — семейная память, стабильна
- **Toll Navigator** — парсинг завершён, деплой pending
- **Philip Bot** — Google Calendar API pending
- **Symphony** — ✅ АКТИВНА, github-watcher + conductor запущены

## Незавершённое
- **Git push заблокирован** — файл >100MB в истории, нужен BFG cleanup
- **115+ файлов незакоммичено** — trading data, quick_logs, submodules
- **Cron автосейв** — haiku-runner.sh восстановлен, cron не триггерит
- Google Search Console регистрация для fixcraftvp.com
- Philip: Google Calendar API
- Костя: механизм прерывания стриминга

## Важные правила
- **git-save = только GitHub**, Vercel только для site-source
- **НЕ редактировать** beast-bot/bot.py, .env, launcher.sh, LaunchAgent plist
- **Git push требует BFG** — pre-receive hook отклоняет из-за >100MB файла в истории
- **Karpathy rules** активны: думай → простота → хирургия → цель
