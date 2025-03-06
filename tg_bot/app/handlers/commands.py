from telegram import Update
from telegram.ext import ContextTypes
from app.utils.keyboard import get_main_menu_keyboard
from app.handlers.base import BaseHandler
import logging

logger = logging.getLogger(__name__)


class CommandHandler(BaseHandler):
    """Обработчик команд бота."""
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /start."""
        try:
            await update.message.reply_text(
                "👋 Привет! Я бот для управления задачами.\n"
                "Используйте меню ниже для навигации:",
                reply_markup=get_main_menu_keyboard()
            )
            logger.info(f"User {update.effective_user.id} started the bot")
        except Exception as e:
            await self.handle_error(update, context, e)
    
    async def show_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показывает главное меню."""
        try:
            await update.message.reply_text(
                "Выберите действие:",
                reply_markup=get_main_menu_keyboard()
            )
        except Exception as e:
            await self.handle_error(update, context, e) 