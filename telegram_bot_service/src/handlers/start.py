from typing import List

import structlog
from client.rest import RestClient, RestClientError
from client.telegram import TelegramClient

from shared_models.api_schemas import AssistantRead, TelegramUserRead

logger = structlog.get_logger()


async def handle_start(
    telegram: TelegramClient, rest: RestClient, chat_id: int, user: TelegramUserRead
) -> None:
    """Handle /start command: list secretaries and prompt user to choose."""
    telegram_id = user.telegram_id  # Use attribute access
    user_id = user.id  # Use attribute access

    try:
        logger.info("Handling /start command", user_id=user_id, telegram_id=telegram_id)

        # 1. Fetch available secretaries from REST service
        secretaries: List[AssistantRead] = []
        try:
            secretaries = await rest.list_secretaries()
        except RestClientError as e:
            logger.error(
                "REST Client Error listing secretaries during /start",
                user_id=user_id,
                error=str(e),
            )
            await telegram.send_message(
                chat_id,
                "Не удалось загрузить список секретарей. Попробуйте /start позже.",
            )
            return  # Stop processing

        if not secretaries:
            logger.warning(
                "No secretaries found in REST service (empty list)."
            )  # Changed from error
            await telegram.send_message(
                chat_id,
                "К сожалению, сейчас нет доступных секретарей. Попробуйте позже.",
            )
            return

        # 2. Format secretaries for display with inline keyboard
        keyboard_buttons = []
        for secretary in secretaries:
            # Use attribute access for schema objects
            description = secretary.description or "(Нет описания)"
            button_text = f"{secretary.name} - {description[:50]}{'...' if len(description) > 50 else ''}"
            callback_data = f"select_secretary_{secretary.id}"
            keyboard_buttons.append(
                [{"text": button_text, "callback_data": callback_data}]
            )

        # 3. Send message with inline keyboard
        message_text = "👋 Привет! Пожалуйста, выбери своего секретаря:"
        await telegram.send_message_with_inline_keyboard(
            chat_id=chat_id, text=message_text, keyboard=keyboard_buttons
        )

        logger.info(
            "Secretaries list sent to user", user_id=user_id, count=len(secretaries)
        )

    except Exception as e:  # Catch any other unexpected errors
        logger.error(
            "Unexpected error handling /start command",
            user_id=user_id,
            telegram_id=telegram_id,
            error=str(e),
            exc_info=True,
        )
        await telegram.send_message(
            chat_id,
            "Извините, произошла непредвиденная ошибка при обработке команды /start. Попробуйте позже.",
        )
