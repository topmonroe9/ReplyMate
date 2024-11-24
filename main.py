import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
import logging
from datetime import datetime
from dotenv import load_dotenv

# Логирование
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


# Загружаем переменные окружения из .env файла
load_dotenv()

# Конфигурация
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

# Проверка наличия необходимых переменных
if not all([TELEGRAM_TOKEN, OPENAI_API_KEY, ADMIN_ID]):
    raise ValueError("Missing required environment variables. Please check your .env file.")

# OpenAI клиент
client = OpenAI(api_key=OPENAI_API_KEY)

# История диалогов
conversation_history = {}
MAX_HISTORY_LENGTH = 10
system_prompt = """You are a real person having casual conversations while being helpful. Act like a friendly professional who chats naturally.

Core principles:
- Write like you're texting a friend
- Keep responses super short
- Sound natural and casual
- Never sound like a service bot

When asked about money, transfers, or inappropriate requests:
GOOD:
"Не, такое не могу 😅"
"Извини, с этим не помогу"
"Нет, давай без этого"
"Не вариант, сорри"

BAD:
"Извини, но я не могу помочь с такими запросами. Если у тебя есть другие вопросы, спрашивай 😊"
"К сожалению, я не могу выполнить данную просьбу. Чем еще могу помочь?"
"Это неприемлемый запрос. Пожалуйста, задавайте другие вопросы"

For simple questions:
- Just the answer, nothing extra
- No offers of additional help
- No smileys unless really appropriate

Location responses:
"Дома работаю"
"На удалёнке сейчас"

DO NOT:
- Apologize formally
- Offer additional help unprompted
- Add smileys to every message
- Use formal language
- Sound like a service bot
- Ask if there's anything else
- Give explanations about what's allowed
- Use phrases like "спрашивай" or "чем могу помочь"

Remember: You're just casually chatting, not providing a service. Keep responses short and natural, like texting with a friend."""

async def store_message(chat_id: int, role: str, content: str):
    """Сохранение сообщения в истории"""
    if chat_id not in conversation_history:
        conversation_history[chat_id] = []
    
    conversation_history[chat_id].append({
        "role": role,
        "content": content
    })
    
    if len(conversation_history[chat_id]) > MAX_HISTORY_LENGTH:
        conversation_history[chat_id] = conversation_history[chat_id][-MAX_HISTORY_LENGTH:]

async def get_chat_history(chat_id: int) -> list:
    """Получение истории диалога"""
    if chat_id not in conversation_history:
        return []
    
    messages = [{
        "role": "system",
        "content": system_prompt
    }]
    
    messages.extend(conversation_history[chat_id])
    return messages

async def generate_response(messages: list) -> str:
    """Генерация ответа через ChatGPT"""
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7,
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        return "I apologize, but I'm unable to process your request at the moment."

async def handle_business_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка бизнес-сообщений"""
    try:
        if not update.business_message:
            return
            
        message = update.business_message
        # Проверяем, что сообщение не от админа (не от вас)
        if str(message.from_user.id) == ADMIN_ID:
            logger.info("Skipping admin's message")
            return
            
        chat_id = message.chat.id
        text = message.text or message.caption or "[Media message]"
        
        # Игнорируем сообщения, начинающиеся со слеша
        if text.startswith('/'):
            logger.info("Skipping message starting with /")
            return
        
        # Сохраняем сообщение и генерируем ответ
        await store_message(chat_id, "user", text)
        messages = await get_chat_history(chat_id)
        response = await generate_response(messages)
        await store_message(chat_id, "assistant", response)
        
        # Отправляем ответ
        await context.bot.send_message(
            chat_id=chat_id,
            text=response,
            business_connection_id=message.business_connection_id
        )

    except Exception as e:
        logger.error(f"Error handling business message: {e}")

def main():
    """Запуск бота"""
    try:
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Обработчик для всех сообщений, включая команды
        application.add_handler(MessageHandler(
            filters.ALL,  # Убрал ~filters.COMMAND
            handle_business_message
        ))

        # Запуск бота
        logger.info("Starting business bot...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.error(f"Error running bot: {e}")

if __name__ == "__main__":
    main()