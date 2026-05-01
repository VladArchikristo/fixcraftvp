---
date: 2026-04-29
type: hot
---

## Последняя сессия
- FixCraftVP блог расширен до 138 статей + 4 страницы сервисов, закоммичено (b0bf8fc), задеплоено
- 20 новых статей добавлены в blog index (page.tsx), контент вставлен
- Hermes бот: диагностирован OAuth token revocation, требует перелогин

## Активные проекты
- **Symphony** — MVP работает, conductor daemon (60s цикл, timeout 3600s), watcher (5 мин), 11 лейблов
- **Trading Bot (Василий)** — AVAX SHORT активна, stop-loss обновлён до breakeven, F&G 26 (fear)
- **FixCraftVP сайт** — 138 статей задеплоено (цель 80 перевыполнена), Google индексация = 0
- **HaulWallet** — v13 аудит готов (arch 8.5, design 8, func 7.5, tests 5/10), нужны тесты
- **Beast Bot** — v10, баг параллельных процессов пофикшен (2bd17e8)
- **Маша** — estimator работает, 75+ площадок для гостевых постов
- **Костя** — стабилен, назначен механизм прерывания стриминга
- **Зина** — семейная память работает

## Незавершённое
- **213+ файлов незакоммичено** — trading data, quick_logs, submodules
- HaulWallet: дописать тесты, настроить iOS/Android credentials, EAS Build
- Philip: Google Calendar API — включить в Cloud Console
- Google индексация 0 страниц — нужен sitemap + Search Console
- Hermes: OAuth токен revoked, нужен ре-логин в сессии

## Важные правила
- **git-save = только GitHub**, Vercel только для site-source
- **НЕ редактировать** beast-bot/bot.py, .env, launcher.sh, LaunchAgent plist
- **Symphony flow:** Telegram → Nexus создаёт Issue → watcher → conductor → агент → результат
- **Боты проверять через PID файлы** (`~/logs/*.pid`), НЕ через `ps aux | grep имя`
