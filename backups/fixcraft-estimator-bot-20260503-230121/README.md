# FixCraft Estimator Bot

Telegram bot for rough handyman estimates from text/photos for FixCraft VP.

## What it does
- Reads photo + caption using GPT vision.
- Uses FixCraft VP pricing rules from `pricing_rules.json`.
- Calculates wall square feet when dimensions are known.
- Warns when photo has no scale reference.
- Outputs client-friendly estimate + internal notes.

## Important limitation
Photo-only square footage is not exact. For wall area, the bot needs at least one:
- width + height in caption;
- tape measure in photo;
- known reference object: standard door 80in, outlet, 4x8 drywall sheet, tile size.

No scale = low-confidence range + questions.

## Setup
```bash
cd "/Users/vladimirprihodko/Папка тест/fixcraftvp/fixcraft-estimator-bot"
cp .env.example .env
# edit .env: BOT_TOKEN and OPENAI_API_KEY
python3 -m pip install python-telegram-bot python-dotenv openai
python3 -m py_compile bot.py estimator_core.py
python3 bot.py
```

## Commands
```text
/start
/rules
/price drywall 4 8
/price hose_reel brick 2
/price tv brick
/estimate replace faucet under kitchen sink, client has faucet
```

## Photo usage
Send a photo with caption:
```text
drywall patch, damaged area roughly 2 ft x 3 ft, needs paint
```

or:
```text
mount 2 small hose reels on brick wall
```

## Pricing source
- FixCraft VP site content:
  - furniture assembly guide: set rates starting at $49;
  - TV mounting: $129–$179 standard, $179–$249 fireplace;
  - IKEA examples: KALLAX/MALM/HEMNES/BESTA/MICKE prices.
- Additional rules are editable local business defaults for Charlotte NC.

## Safety
- This is a rough estimator, not a final quote.
- Bot only responds to Vlad Telegram ID `244710532` by default.
- Stores incoming photos in `incoming_photos/`.
