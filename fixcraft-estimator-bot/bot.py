import os
import json
import logging
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from openai import OpenAI

from estimator_core import estimate_from_structured, format_estimate, load_rules
from vision_proxy import ensure_public_base_url, publish_image, cleanup_old_images

BASE = Path(__file__).resolve().parent
LOG_DIR = Path.home() / 'logs'
LOG_DIR.mkdir(exist_ok=True)
load_dotenv(BASE / '.env')

BOT_TOKEN = os.getenv('BOT_TOKEN')
# Default = free/no-extra-API-cost mode through Vlad's local ChatGPT subscription proxy.
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'http://127.0.0.1:10531/v1')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', 'dummy')
VISION_MODEL = os.getenv('VISION_MODEL', 'gpt-5.5')
TEXT_MODEL = os.getenv('TEXT_MODEL', VISION_MODEL)
OWNER_ID = int(os.getenv('OWNER_TELEGRAM_ID', '244710532'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    handlers=[logging.FileHandler(LOG_DIR / 'fixcraft-estimator-bot.log'), logging.StreamHandler()],
)
log = logging.getLogger('fixcraft-estimator')

client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

SYSTEM = """You are FixCraft VP Estimator Bot for Vlad, a handyman business in Charlotte NC.
Your job: analyze customer photos/descriptions and produce rough internal estimates.
Rules:
- Do NOT pretend exact measurement from photo unless there is scale reference.
- If no scale, ask for width/height or give low-confidence range.
- Use FixCraft VP pricing rules provided in JSON.
- Always identify: job type, visible surface/material, quantity, tools/materials, risks, missing info.
- For walls: square feet = width_ft * height_ft. If only standard objects visible, estimate confidence low.
- Output JSON only with keys: job_type, confidence, visible_scope, assumed_dimensions, sqft, surface, quantity, tools, materials, risks, missing_questions, recommended_price_low, recommended_price_high, client_message, internal_notes.
- Estimates are ballpark; Vlad finalizes.
"""


def is_owner(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id == OWNER_ID)


def rules_text():
    return json.dumps(load_rules(), ensure_ascii=False)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    await update.message.reply_text(
        "Я FixCraft Estimator. Отправь фото + описание.\n\n"
        "Примеры:\n"
        "• wall 12x8 drywall patch 2x3 ft\n"
        "• hose reel on brick, 2 units\n"
        "• paint wall width 14 height 9\n\n"
        "Команды: /estimate, /price, /rules, /vision_status"
    )


async def rules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    r = load_rules()
    await update.message.reply_text(
        f"FixCraft VP pricing loaded. Hourly: ${r['business']['hourly_rate']}/hr, minimum: ${r['business']['minimum_service_call']}."
    )


async def vision_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    try:
        base = ensure_public_base_url()
        cleanup_old_images()
        await update.message.reply_text(
            "Vision proxy OK\n"
            f"Model: {VISION_MODEL}\n"
            f"Base URL: {OPENAI_BASE_URL}\n"
            f"Image tunnel: {base}"
        )
    except Exception as e:
        log.exception('vision status failed')
        await update.message.reply_text(f"Vision proxy error: {type(e).__name__}: {e}")


async def price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    text = ' '.join(context.args).lower()
    # simple parser examples: /price drywall 4 8 ; /price hose_reel brick 2
    parts = text.split()
    if not parts:
        await update.message.reply_text('Usage: /price drywall 4 8 OR /price hose_reel brick 2 OR /price tv brick')
        return
    job = parts[0]
    surface = None
    qty = 1
    width = height = None
    for p in parts[1:]:
        if p in ['brick','masonry','concrete','wood','vinyl','drywall']:
            surface = p
        elif p.isdigit():
            if width is None:
                width = float(p)
            elif height is None:
                height = float(p)
            else:
                qty = int(p)
    if job in ['hose', 'hose_reel'] and parts[-1].isdigit():
        qty = int(parts[-1])
    result = estimate_from_structured(job, width, height, qty, surface)
    await update.message.reply_text(format_estimate(result))


async def estimate_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    text = update.message.text or ''
    try:
        resp = client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[
                {'role': 'system', 'content': SYSTEM + '\nPricing rules JSON:\n' + rules_text()},
                {'role': 'user', 'content': text},
            ],
            response_format={'type': 'json_object'},
            temperature=0.2,
        )
        data = json.loads(resp.choices[0].message.content)
        await update.message.reply_text(format_ai_estimate(data))
    except Exception as e:
        log.exception('text estimate failed')
        await update.message.reply_text(f'Ошибка оценки текста: {type(e).__name__}. Попробуй /price или пришли фото с описанием.')


def format_ai_estimate(data: dict) -> str:
    low = data.get('recommended_price_low')
    high = data.get('recommended_price_high')
    lines = ['📋 FixCraft VP estimate']
    lines.append(f"Job: {data.get('job_type','unknown')}")
    lines.append(f"Confidence: {data.get('confidence','unknown')}")
    if data.get('sqft'):
        lines.append(f"Area: ~{data.get('sqft')} sq ft")
    if data.get('surface'):
        lines.append(f"Surface: {data.get('surface')}")
    if low and high:
        lines.append(f"Ballpark: ${low}–${high}")
    if data.get('visible_scope'):
        lines.append('\nVisible scope: ' + str(data.get('visible_scope')))
    if data.get('tools'):
        lines.append('\nTools: ' + ', '.join(map(str, data.get('tools', []))))
    if data.get('materials'):
        lines.append('Materials: ' + ', '.join(map(str, data.get('materials', []))))
    if data.get('risks'):
        lines.append('Risks: ' + ', '.join(map(str, data.get('risks', []))))
    if data.get('missing_questions'):
        lines.append('\nAsk client: ' + ' | '.join(map(str, data.get('missing_questions', []))))
    if data.get('client_message'):
        lines.append('\nClient message:\n' + str(data.get('client_message')))
    if data.get('internal_notes'):
        lines.append('\nInternal notes:\n' + str(data.get('internal_notes')))
    lines.append('\nFinal quote after Vlad confirms scope.')
    return '\n'.join(lines)[:3900]


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return
    caption = update.message.caption or 'No caption. Analyze the job from photo.'
    photo = update.message.photo[-1]
    f = await context.bot.get_file(photo.file_id)
    img_dir = BASE / 'incoming_photos'
    img_dir.mkdir(exist_ok=True)
    img_path = img_dir / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{photo.file_unique_id}.jpg"
    await f.download_to_drive(str(img_path))
    try:
        public_url = publish_image(img_path)
        resp = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {'role': 'system', 'content': SYSTEM + '\nPricing rules JSON:\n' + rules_text()},
                {'role': 'user', 'content': [
                    {'type': 'text', 'text': caption},
                    {'type': 'image_url', 'image_url': {'url': public_url}},
                ]},
            ],
            response_format={'type': 'json_object'},
            temperature=0.15,
        )
        data = json.loads(resp.choices[0].message.content)
        await update.message.reply_text(format_ai_estimate(data))
    except Exception as e:
        log.exception('photo estimate failed')
        await update.message.reply_text(f'Фото-анализ упал: {type(e).__name__}. Фото сохранено: {img_path.name}.')


def main():
    if not BOT_TOKEN:
        raise SystemExit('BOT_TOKEN missing in .env')
    (LOG_DIR / 'fixcraft-estimator-bot.pid').write_text(str(os.getpid()))
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('rules', rules_cmd))
    app.add_handler(CommandHandler('vision_status', vision_status_cmd))
    app.add_handler(CommandHandler('price', price_cmd))
    app.add_handler(CommandHandler('estimate', estimate_text))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, estimate_text))
    log.info('FixCraft Estimator Bot starting')
    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
