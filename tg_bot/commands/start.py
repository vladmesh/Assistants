from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

from app.utils.keyboard import get_main_menu_keyboard
from app.rest_client import RestClient


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Приветственное сообщение и создание пользователя."""
    telegram_id = update.message.from_user.id
    username = update.message.from_user.username
    
    # Получить или создать пользователя через REST API
    rest_client = RestClient()
    user = rest_client.get_or_create_user(telegram_id=telegram_id, username=username)

    # Отправляем приветственное сообщение с клавиатурой
    await update.message.reply_text(
        "👋 Привет! Я бот для управления задачами.\n"
        "Используйте меню ниже для навигации:",
        reply_markup=get_main_menu_keyboard()
    )

