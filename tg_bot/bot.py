from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from rest_service.rest_service import RestService
import os

async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f'Hello {update.effective_user.first_name}')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Приветственное сообщение и создание пользователя."""
    telegram_id = str(update.message.from_user.id)
    username = update.message.from_user.username
    rest_service = RestService("http://rest_service:8000/api")
    # Получить или создать пользователя
    user = rest_service.get_or_create_user(telegram_id=telegram_id, username=username)

    await update.message.reply_text(
        f"Привет, {user.username or 'пользователь'}! Я помогу управлять твоими задачами. Вот что я умею:\n"
        "/tasks - посмотреть задачи\n"
    )


token = os.getenv('TELEGRAM_TOKEN')
app = ApplicationBuilder().token(token).build()

app.add_handler(CommandHandler("hello", hello))
app.add_handler(CommandHandler("start", start))

app.run_polling()