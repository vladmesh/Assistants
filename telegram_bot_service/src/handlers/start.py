from typing import Any, Dict

import structlog
from client.rest import RestClient
from client.telegram import TelegramClient

logger = structlog.get_logger()


async def handle_start(
    telegram: TelegramClient, rest: RestClient, chat_id: int, user: Dict[str, Any]
) -> None:
    """Handle /start command: list secretaries and prompt user to choose."""
    telegram_id = user.get("telegram_id")  # Use telegram_id from user dict
    user_id = user.get("id")  # internal user id

    try:
        logger.info("Handling /start command", user_id=user_id, telegram_id=telegram_id)

        # 1. Fetch available secretaries from REST service
        secretaries = await rest.list_secretaries()

        if not secretaries:
            logger.error("No secretaries found in REST service.")
            await telegram.send_message(
                chat_id,
                "К сожалению, сейчас нет доступных секретарей. Попробуйте позже.",
            )
            return

        # 2. Format secretaries for display with inline keyboard
        keyboard_buttons = []
        for secretary in secretaries:
            # Ensure description is available, provide fallback if needed
            description = secretary.get("description") or "(Нет описания)"
            button_text = f"{secretary.get('name')} - {description[:50]}{'...' if len(description) > 50 else ''}"
            callback_data = f"select_secretary_{secretary.get('id')}"
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

    except Exception as e:
        logger.error(
            "Error handling start command",
            user_id=user_id,
            telegram_id=telegram_id,
            error=str(e),
            exc_info=True,
        )
        await telegram.send_message(
            chat_id,
            "Извините, произошла ошибка при обработке команды /start. Попробуйте позже.",
        )
