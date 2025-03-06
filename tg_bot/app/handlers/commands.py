from telegram import Update
from telegram.ext import ContextTypes

from app.utils.keyboard import get_main_menu_keyboard


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    await update.message.reply_text(
        "👋 Привет! Я бот для управления задачами.\n"
        "Используйте меню ниже для навигации:",
        reply_markup=get_main_menu_keyboard()
    )


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает главное меню."""
    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=get_main_menu_keyboard()
    ) 