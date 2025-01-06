import warnings

from telegram import Update
from telegram.ext import ContextTypes

from rest_service.rest_service import RestService


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Приветственное сообщение и создание пользователя."""
    warnings.warn("start of start command")
    telegram_id = update.message.from_user.id
    username = update.message.from_user.username
    rest_service = RestService()
    # Получить или создать пользователя
    user = rest_service.get_or_create_user(telegram_id=telegram_id, username=username)

    await update.message.reply_text(
        f"Привет, {user.username or 'пользователь'}! Я помогу управлять твоими задачами. Вот что я умею:\n"
        "/tasks - посмотреть активные задачи\n"
        "/new_task - добавить новую задачу\n"
    )
