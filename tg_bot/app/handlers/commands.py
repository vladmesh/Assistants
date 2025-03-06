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
            # Проверяем, существует ли пользователь
            user = self.rest_client.get_user(telegram_id=update.effective_user.id)
            
            if user:
                message = (
                    "С возвращением! 👋\n"
                    "Используйте меню ниже для управления задачами:"
                )
            else:
                # Создаем нового пользователя
                user = self.rest_client.create_user(
                    telegram_id=update.effective_user.id,
                    username=update.effective_user.username
                )
                message = (
                    "Добро пожаловать! 👋\n"
                    "Я бот для управления задачами. С моей помощью вы можете:\n"
                    "• Создавать новые задачи\n"
                    "• Просматривать список задач\n"
                    "• Отмечать задачи как выполненные\n\n"
                    "Используйте меню ниже для навигации:"
                )
            
            await update.message.reply_text(
                message,
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