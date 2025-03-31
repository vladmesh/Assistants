from typing import Any, Dict

import structlog
from client.rest import RestClient
from client.telegram import TelegramClient

logger = structlog.get_logger()


async def handle_start(
    telegram: TelegramClient, rest: RestClient, chat_id: int, user: Dict[str, Any]
) -> None:
    """Handle /start command."""
    telegram_id = user.get("id")
    username = user.get("username")

    try:
        # Get or create user in REST service
        user_data = await rest.get_or_create_user(telegram_id, username)
        is_new_user = user_data.get("id") == telegram_id

        # Send appropriate greeting
        if is_new_user:
            message = (
                "👋 Привет! Я ваш персональный ассистент.\n\n"
                "Я могу помочь вам с:\n"
                "📅 Управлением встречами и событиями\n"
                "📝 Созданием заметок\n"
                "🔍 Поиском информации\n\n"
                "Чем могу помочь?"
            )
        else:
            message = "👋 С возвращением!\n\n" "Чем могу помочь сегодня?"

        await telegram.send_message(chat_id, message)
        logger.info(
            "Start command handled", telegram_id=telegram_id, is_new_user=is_new_user
        )

    except Exception as e:
        error_message = (
            "Извините, произошла ошибка при обработке команды. Попробуйте позже."
        )
        await telegram.send_message(chat_id, error_message)
        logger.error(
            "Error handling start command", telegram_id=telegram_id, error=str(e)
        )
