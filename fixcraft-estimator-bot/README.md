# FixCraft Estimator Bot

Telegram bot for rough handyman estimates from text/photos for FixCraft VP.

## Mode
Default mode uses Vlad's existing ChatGPT Plus/Pro subscription through local `openai-oauth` proxy:

```text
OPENAI_BASE_URL=http://127.0.0.1:10531/v1
VISION_MODEL=gpt-5.5
OPENAI_API_KEY=dummy
```

Photo vision works by publishing each Telegram image to a temporary local image host exposed through ngrok, then sending the HTTPS image URL to GPT-5.5. This avoids OpenAI API billing.

## Files
- `bot.py` — Telegram bot.
- `estimator_core.py` — deterministic pricing helpers.
- `pricing_rules.json` — FixCraft VP rates and service ranges.
- `vision_proxy.py` — local static server + ngrok helper.
- `.env.example` — config template.
- `com.vladimir.fixcraft-estimator-bot.plist.template` — LaunchAgent template.

## Commands
- `/start` — help.
- `/rules` — show loaded hourly/minimum.
- `/vision_status` — start/check local image server + ngrok tunnel.
- `/price drywall 4 8` — deterministic estimate.
- `/price hose_reel brick 2` — deterministic estimate.
- `/estimate <description>` — AI estimate from text.
- Send photo + caption — AI vision estimate.

## Setup after BotFather token
```bash
cd "/Users/vladimirprihodko/Папка тест/fixcraftvp/fixcraft-estimator-bot"
cp .env.example .env
# edit .env: BOT_TOKEN=...
python3 bot.py
```

## LaunchAgent
After `.env` is ready:

```bash
cp com.vladimir.fixcraft-estimator-bot.plist.template ~/Library/LaunchAgents/com.vladimir.fixcraft-estimator-bot.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.vladimir.fixcraft-estimator-bot.plist
launchctl kickstart -k gui/$(id -u)/com.vladimir.fixcraft-estimator-bot
```

## Measurement truth
The bot must not invent exact square footage from a photo without scale. Good scale references:
- tape measure in frame;
- known wall width/height in caption;
- standard door height 80 in;
- drywall sheet 4x8;
- tile size;
- outlet/standard object only as low-confidence reference.

If no scale exists, the bot should ask for dimensions or give a low-confidence range.
