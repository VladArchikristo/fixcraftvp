---
date: 2026-05-01
type: hot
---

## Последняя сессия
- Глубокая диагностика Маши: убиты 77+ зомби-процессов, dual-method self-eviction (pgrep + PID file), enhanced stdout/stderr logging
- Сайт FixCraft восстановлен с нуля после corruption, Google Ads кампания создана
- Symphony MVP работает, Trading Bot анализ ETH/XRP/AVAX завершён

## Активные проекты
- **FixCraftVP сайт** — восстановлен в fixcraft/, Vercel деплой PENDING (нужен токен)
- **Symphony** — MVP работает (github-watcher + conductor), 11 лейблов
- **Trading Bot (Василий)** — risk-off, STOP_NEW_ENTRIES, анализ ETH/XRP/AVAX
- **Маша** — enhanced logging deployed, ждём следующий краш для stdout capture
- **Костя** — зависает 10-11 мин (фикс НЕ применён)
- **Beast Bot** — v10, баг параллельных Claude-процессов (Issue #3)
- **Зина** — семейная память работает

## Незавершённое
- **Vercel деплой fixcraft/** — нужен токен: vercel.com/account/tokens
- **Фикс Кости** — убрать retry при exit 1 в coder-bot/telegram_bot.py:~531-539, CLAUDE_TIMEOUT 600→180
- **Git commit** — masha-bot/bot.py изменён, не закоммичен
- **Маша краш** — ждём exit 1 чтобы увидеть stdout с реальной ошибкой
- **SEO** — Google индексация = 0 страниц, нужен sitemap + Search Console
- **hero.mp4** — положить в fixcraft/public/videos/ → раскомментировать video тег
- **Beast баг** — убивать active_claude_proc перед новым запуском

## Важные правила
- **git-save = только GitHub**, Vercel только для деплоя fixcraft/
- **НЕ редактировать** beast-bot/bot.py, .env, launcher.sh, LaunchAgent plist
- **Боты проверять через PID файлы** (`~/logs/*.pid`), НЕ через `ps aux | grep имя`
- **Karpathy rules:** думай → простота → хирургия → цель
