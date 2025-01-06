from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes



async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Список задач", callback_data="view_tasks")],
        [InlineKeyboardButton("Добавить задачу", callback_data="add_task")],
        [InlineKeyboardButton("Настройки", callback_data="settings")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        # Если это сообщение (например, команда /start)
        await update.message.reply_text("Главное меню:", reply_markup=reply_markup)
    elif update.callback_query:
        # Если это callback_query (нажатие инлайн-кнопки)
        query = update.callback_query
        await query.answer()  # Подтверждаем callback
        await query.edit_message_text("Главное меню:", reply_markup=reply_markup)

