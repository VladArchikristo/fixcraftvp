# CODEX ONE-SHOT PROMPT: FixCraft AI Estimator Bot

## Goal
Build a Telegram bot that turns job-site photos into detailed, professional repair estimates for a handyman business in Charlotte, NC.

## Business Context
- Company: FixCraft VP (EAST VLADIPRI INC)
- Location: Charlotte, NC 28277 (Ballantyne area)
- Services: Handyman, drywall, painting, flooring, door repair, minor plumbing/electrical, tile, carpentry
- Target: Residential clients within 25 miles of 28277

## How It Works
1. User (Vlad or client) sends a photo to the Telegram bot with a caption like "Need to fix this door frame"
2. Bot sends photo + caption to OpenAI GPT-4o Vision API
3. AI analyzes the photo and returns a structured breakdown of:
   - Job type and scope
   - Materials needed (with quantities)
   - Labor hours breakdown
   - Difficulty level
   - Hidden issues to watch for
4. Bot calculates pricing using Charlotte NC handyman rates
5. Bot replies with a formatted estimate message
6. Bot generates a branded PDF estimate and sends it

## Tech Stack
- Python 3.9+
- python-telegram-bot (v20+)
- OpenAI API (GPT-4o)
- ReportLab (PDF generation)
- SQLite (simple local database)
- python-dotenv

## Directory Structure
```
~/fixcraft-estimator-bot/
├── bot.py              # Main bot entry point
├── config.py           # Pricing config, constants
├── ai_analyzer.py      # OpenAI Vision wrapper
├── pricing.py          # Estimate calculation engine
├── pdf_generator.py    # Branded PDF generation
├── database.py         # SQLite models & queries
├── requirements.txt
├── .env
└── assets/
    └── logo.png        # FixCraft VP logo for PDF
```

## Pricing Rules (Charlotte NC Handyman)
```python
LABOR_RATE_STANDARD = 95.0      # $/hour
LABOR_RATE_EMERGENCY = 130.0    # $/hour same-day
MATERIAL_MARKUP = 1.30          # 30% markup on materials
OVERHEAD_PERCENT = 0.15         # 15%
PROFIT_MARGIN = 0.20            # 20% on subtotal
MINIMUM_SERVICE_CALL = 175.0    # Minimum job charge
```

## Core Features to Build

### 1. Telegram Bot Handler (`bot.py`)
```python
# Commands:
/start - Welcome message with instructions
/help - How to use the bot
/newest - Start new estimate (prompts for photo)
/history - Show last 10 estimates
/settings - Adjust pricing config (admin only)

# Photo handler:
# When photo received:
# 1. Download photo
# 2. Send "Analyzing photo..." message
# 3. Call AI analyzer
# 4. Calculate pricing
# 5. Send formatted estimate
# 6. Generate and send PDF
# 7. Save to database
```

### 2. AI Analyzer (`ai_analyzer.py`)
Use OpenAI GPT-4o with this exact system prompt:
```
You are an expert handyman estimator with 20+ years experience in Charlotte, NC.
Analyze the provided construction/repair photo and description.

Identify:
1. Exact job type (drywall_repair, door_frame, painting, flooring, plumbing, electrical, tile, carpentry, etc.)
2. Detailed description of work needed
3. Complete materials list with realistic quantities for Charlotte NC market
4. Labor hour breakdown by task (be realistic, not optimistic)
5. Difficulty: easy/medium/hard
6. Any hidden issues that might increase cost
7. Whether permit is likely needed

Return STRICT JSON only:
{
  "job_type": "drywall_repair",
  "title": "Drywall Repair - Bedroom Wall",
  "description": "Repair water damaged drywall section approximately 4x3 feet...",
  "materials": [
    {"item": "Sheetrock 4x8 1/2in", "qty": 1, "unit": "sheet", "unit_cost": 14.50, "notes": "Cut to size"},
    {"item": "Joint compound 3.5gal", "qty": 0.5, "unit": "bucket", "unit_cost": 22.00, "notes": "Only need half bucket"}
  ],
  "labor_breakdown": [
    {"task": "Cut out damaged section", "hours": 0.5},
    {"task": "Install new drywall", "hours": 1.0},
    {"task": "Tape, mud, sand", "hours": 2.0},
    {"task": "Prime and paint match", "hours": 1.5}
  ],
  "total_labor_hours": 5.0,
  "difficulty": "medium",
  "hidden_issues": ["Possible moisture source behind wall", "Paint matching may require full wall repaint"],
  "permit_required": false,
  "notes": "Client should verify source of water damage before repair"
}
```

### 3. Pricing Engine (`pricing.py`)
```python
def calculate_estimate(ai_analysis: dict, is_emergency: bool = False) -> dict:
    """
    Calculate full estimate from AI analysis.
    Returns dict with:
    - materials_subtotal
    - materials_with_markup
    - labor_subtotal
    - overhead_amount
    - profit_amount
    - total
    - line_items (detailed)
    """
```

### 4. PDF Generator (`pdf_generator.py`)
Use ReportLab to generate professional PDF with:
- FixCraft VP header (placeholder text if no logo)
- Client info section
- Job description
- Itemized table (Materials, Labor, Overhead, Profit)
- Total in large bold
- Terms: "Valid for 30 days. 50% deposit required. Final price subject to on-site inspection."
- Footer with contact info

### 5. Database (`database.py`)
SQLite with tables:
```sql
CREATE TABLE estimates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id BIGINT,
    photo_path TEXT,
    description TEXT,
    ai_analysis TEXT,  -- JSON
    line_items TEXT,   -- JSON
    total_amount REAL,
    status TEXT DEFAULT 'draft',  -- draft / sent / accepted / declined
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE pricing_config (
    id INTEGER PRIMARY KEY,
    labor_rate_standard REAL DEFAULT 95.0,
    labor_rate_emergency REAL DEFAULT 130.0,
    material_markup REAL DEFAULT 1.30,
    overhead_percent REAL DEFAULT 0.15,
    profit_margin REAL DEFAULT 0.20,
    minimum_service_call REAL DEFAULT 175.0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Message Format (Telegram Reply)
```
🔨 FixCraft VP — Estimate

📋 Job: {title}
📍 Location: Charlotte, NC

📊 BREAKDOWN:

🧱 MATERIALS:
{line items}
   Subtotal: ${materials_subtotal}
   Markup (30%): ${markup_amount}

👷 LABOR ({total_hours} hrs @ ${rate}/hr):
{breakdown}
   Subtotal: ${labor_subtotal}

📎 Overhead (15%): ${overhead}
💰 Profit (20%): ${profit}

═══════════════════════
💵 TOTAL: ${total}
═══════════════════════

⚠️ Valid for 30 days
📝 50% deposit to schedule
🔍 Final price subject to on-site inspection

📄 PDF estimate sent above ⬆️
```

## Environment Variables (.env)
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
OPENAI_API_KEY=your_openai_key_here
ADMIN_CHAT_ID=your_telegram_chat_id
```

## Admin Features
Only ADMIN_CHAT_ID can:
- View all estimates
- Change pricing config via /settings
- View stats (/stats command)

## Requirements.txt
```
python-telegram-bot==20.7
openai>=1.0.0
reportlab>=4.0.0
python-dotenv>=1.0.0
pillow>=10.0.0
```

## IMPORTANT IMPLEMENTATION NOTES
1. Download photo from Telegram, save locally, pass file path to OpenAI
2. Handle errors gracefully — if AI fails, return "Sorry, couldn't analyze this photo. Please try with better lighting or a clearer description."
3. Rate limit: max 5 estimates per chat per hour (prevent spam)
4. Always include disclaimer about on-site inspection
5. Use asyncio throughout (python-telegram-bot v20 is async)
6. Clean up downloaded photos after processing (keep for 24h then delete)
7. Save estimates to DB immediately after generation
8. Send PDF as document, not photo

## TESTING CHECKLIST
After building, verify:
- [ ] /start works and shows welcome
- [ ] Photo + caption generates estimate
- [ ] Pricing math is correct (materials + markup + labor + overhead + profit)
- [ ] PDF is generated and sent
- [ ] Estimate saved to database
- [ ] /history shows past estimates
- [ ] /settings updates pricing config
- [ ] Non-admin cannot access admin commands
- [ ] Error handling works for bad photos

## FINAL INSTRUCTION FOR CODEX
Build ALL files listed above. Create the complete working bot. Do NOT skip any files. Make sure the bot can be started with `python bot.py` after installing requirements and creating .env.
