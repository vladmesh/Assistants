from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

from rest_service.rest_service import RestService


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Приветственное сообщение и создание пользователя."""
    telegram_id = update.message.from_user.id
    chat_id = update.message.chat_id
    username = update.message.from_user.username
    rest_service = RestService()
    # Получить или создать пользователя
    user = rest_service.get_or_create_user(telegram_id=telegram_id, username=username, chat_id=chat_id)

    keyboard = [
        [KeyboardButton("Показать меню")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    # Отправляем приветственное сообщение с клавиатурой
    await update.message.reply_text(f"Your telegram id:{telegram_id}, your chat id:{chat_id}, your username:{username}")
    await update.message.reply_text(
        "Привет! Нажми 'Показать меню', чтобы увидеть доступные действия.",
        reply_markup=reply_markup,
    )

