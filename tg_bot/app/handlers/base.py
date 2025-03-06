from typing import Any, Dict, Optional
from telegram import Update
from telegram.ext import ContextTypes
from app.utils.keyboard import get_main_menu_keyboard
import logging

logger = logging.getLogger(__name__)


class BaseHandler:
    """Базовый класс для обработчиков с поддержкой состояний и обработки ошибок."""
    
    def __init__(self, rest_client):
        self.rest_client = rest_client
    
    async def handle_error(self, update: Update, context: ContextTypes.DEFAULT_TYPE, error: Exception) -> None:
        """Обрабатывает ошибки и отправляет уведомление пользователю."""
        error_message = f"Произошла ошибка: {str(error)}"
        logger.error(error_message, exc_info=True)
        
        if update.callback_query:
            await update.callback_query.message.reply_text(
                error_message,
                reply_markup=get_main_menu_keyboard()
            )
        else:
            await update.message.reply_text(
                error_message,
                reply_markup=get_main_menu_keyboard()
            )
    
    def get_user_state(self, context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
        """Получает текущее состояние пользователя."""
        if "state" not in context.user_data:
            context.user_data["state"] = {}
        return context.user_data["state"]
    
    def set_user_state(self, context: ContextTypes.DEFAULT_TYPE, state: Dict[str, Any]) -> None:
        """Устанавливает состояние пользователя."""
        context.user_data["state"] = state
    
    def clear_user_state(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Очищает состояние пользователя."""
        context.user_data.clear()
    
    def validate_input(self, text: str, min_length: int = 1, max_length: int = 100) -> bool:
        """Проверяет корректность входных данных."""
        return min_length <= len(text) <= max_length 