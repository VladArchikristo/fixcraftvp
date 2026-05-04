#!/usr/bin/env python3
"""
ДЖЕК — новый бот-программист на GPT-5.5
Абсолютно чистый код, без заимствований
"""

import os
import logging
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('/Users/vladimirprihodko/logs/jack-bot.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# Токен из .env
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
if not BOT_TOKEN:
    env_path = '/Users/vladimirprihodko/Папка тест/fixcraftvp/jack-bot/.env'
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if line.startswith('BOT_TOKEN='):
                    BOT_TOKEN = line.split('=', 1)[1].strip()
                    break

log.info(f"Jack bot token: {BOT_TOKEN[:20]}...")

# GPT-5.5 через локальный proxy
OPENAI_URL = 'http://localhost:10531/v1/chat/completions'

# История диалогов
chat_history = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    await update.message.reply_text(
        "🚀 **ДЖЕК НА СВЯЗИ!**\n\n"
        "Твой программист на GPT-5.5.\n\n"
        "Кидай код, задачи, вопросы — разберёмся!"
    )

async def clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /clear"""
    user_id = update.effective_user.id
    if user_id in chat_history:
        chat_history[user_id] = []
    await update.message.reply_text("✅ История очищена")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    user_id = update.effective_user.id
    user_message = update.message.text
    
    log.info(f"Сообщение от {user_id}: {user_message[:100]}...")
    
    # Индикатор "печатает..."
    await update.message.chat.send_action(action='typing')
    
    try:
        # Инициализация истории
        if user_id not in chat_history:
            chat_history[user_id] = []
        
        # Добавляем сообщение пользователя
        chat_history[user_id].append({"role": "user", "content": user_message})
        
        # Ограничиваем историю 15 сообщениями
        if len(chat_history[user_id]) > 15:
            chat_history[user_id] = chat_history[user_id][-15:]
        
        # Системный промпт
        system_prompt = (
            "Ты ДЖЕК — программист-гений на GPT-5.5. "
            "Отвечаешь чётко, по делу, с примерами кода когда нужно. "
            "Язык: русский."
        )
        
        # Запрос к GPT-5.5
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                OPENAI_URL,
                headers={
                    "Authorization": "Bearer x",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-5.5",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        *chat_history[user_id]
                    ],
                    "max_tokens": 4000
                }
            )
            response.raise_for_status()
            data = response.json()
            ai_response = data["choices"][0]["message"]["content"]
        
        # Добавляем ответ в историю
        chat_history[user_id].append({"role": "assistant", "content": ai_response})
        
        # Отправляем ответ
        await update.message.reply_text(ai_response)
        log.info(f"Ответ отправлен {user_id}")
        
    except Exception as e:
        log.error(f"Ошибка: {e}", exc_info=True)
        error_msg = f"⚠️ Ошибка:\n{str(e)[:300]}"
        await update.message.reply_text(error_msg)

def main():
    """Запуск бота"""
    log.info("Запуск Джека...")
    
    # Создаём приложение
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear_history))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Запуск polling
    log.info("Джек запущен. Polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
