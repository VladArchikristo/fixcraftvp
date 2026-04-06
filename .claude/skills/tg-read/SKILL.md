---
name: tg-read
description: Read public Telegram channel posts. Use when asked to read a Telegram channel, check news from Telegram, show latest posts from channel, or monitor @username on Telegram. Trigger phrases: "читай канал", "покажи посты", "что в канале", "новости из телеграм", "tg-read", "прочитай телеграм канал", "последние посты".
---

# Telegram Channel Reader

Read the latest posts from a public Telegram channel.

## How to use

When invoked with a channel username (e.g. `kopeechkav` or `@kopeechkav`):
1. Strip the `@` if present
2. Fetch `https://t.me/s/{username}` using WebFetch
3. Extract and display the latest posts with dates and text

If no username is provided, show the list of saved channels and ask which one to read:
- **@kopeechkav** — новостной канал, графики, аналитика рынка
- **@capitalifornia** — инвестиционный канал, принципы торговли по новостям

## Output format

Show posts concisely, newest first:

📢 @{channel} — последние посты:

[дата] Текст поста...

[дата] Текст поста...

After showing posts, add a brief trading comment if the posts contain market-relevant news (stocks, crypto, commodities, geopolitics).

## Notes
- Only works with public channels accessible via t.me/s/username
- Use WebFetch tool with URL: https://t.me/s/{username}
- Prompt for WebFetch: "Extract the latest 10 posts from this Telegram channel. Return each post with its date and full text."
