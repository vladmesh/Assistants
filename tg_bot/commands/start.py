from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

from rest_service.rest_service import RestService


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Приветственное сообщение и создание пользователя."""
    telegram_id = update.message.from_user.id
    username = update.message.from_user.username
    rest_service = RestService()
    # Получить или создать пользователя
    user = rest_service.get_or_create_user(telegram_id=telegram_id, username=username)

    keyboard = [
        [KeyboardButton("Показать меню")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    # Отправляем приветственное сообщение с клавиатурой
    await update.message.reply_text(
        "Привет! Нажми 'Показать меню', чтобы увидеть доступные действия.",
        reply_markup=reply_markup,
    )

