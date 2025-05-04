from typing import Any, List

import structlog

# Обрати внимание: пути импорта изменились на clients
from clients.rest import RestClient, RestClientError
from clients.telegram import TelegramClient

# Импортируем фабрику клавиатур (будет создана позже)
from keyboards.secretary_selection import create_secretary_selection_keyboard

# Используем user_service
from services import user_service

# Import shared models if needed for type hints (AssistantRead?)
from shared_models.api_schemas import AssistantRead, TelegramUserRead

logger = structlog.get_logger()


async def handle_start(**context: Any) -> None:
    """Handles the /start command.

    - Gets or creates the user via REST.
    - Lists available secretaries.
    - Prompts the user to choose a secretary via inline keyboard.
    """
    telegram: TelegramClient = context["telegram"]
    rest: RestClient = context["rest"]
    chat_id: int = context["chat_id"]
    user_id_str: str = context["user_id_str"]
    username: str | None = context["username"]

    try:
        telegram_id = int(user_id_str)
        logger.info("Handling /start command", chat_id=chat_id, telegram_id=telegram_id)

        # 1. Get or create user
        user: TelegramUserRead | None = None
        try:
            user = await user_service.get_or_create_telegram_user(
                rest, telegram_id, username
            )
        except RestClientError as e:
            logger.error(
                "REST Client Error during get_or_create_user for /start",
                telegram_id=telegram_id,
                error=str(e),
            )
            await telegram.send_message(
                chat_id,
                "Произошла ошибка при получении данных пользователя. Попробуйте позже.",
            )
            return
        except ValueError:
            logger.error("Invalid telegram_id format", user_id_str=user_id_str)
            await telegram.send_message(
                chat_id, "Произошла ошибка: неверный формат ID."
            )
            return

        if (
            not user
        ):  # Should not happen with get_or_create unless REST returns unexpected null
            logger.error(
                "User object is unexpectedly None after get_or_create_user",
                telegram_id=telegram_id,
            )
            await telegram.send_message(
                chat_id, "Произошла внутренняя ошибка при обработке пользователя."
            )
            return

        user_id = user.id  # Internal UUID

        # 2. Fetch available secretaries from REST service
        secretaries: List[AssistantRead] = []
        try:
            secretaries = await user_service.list_available_secretaries(rest)
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
                "No secretaries found in REST service (empty list).", user_id=user_id
            )
            await telegram.send_message(
                chat_id,
                "К сожалению, сейчас нет доступных секретарей. Попробуйте позже.",
            )
            return

        # 3. Create inline keyboard using the factory
        keyboard_buttons = create_secretary_selection_keyboard(secretaries)

        # 4. Send message with inline keyboard
        message_text = "👋 Привет! Пожалуйста, выбери своего секретаря:"
        await telegram.send_message_with_inline_keyboard(
            chat_id=chat_id, text=message_text, keyboard=keyboard_buttons
        )

        logger.info(
            "Secretaries list sent to user", user_id=user_id, count=len(secretaries)
        )

    except Exception as e:  # Catch any other unexpected errors during the process
        logger.error(
            "Unexpected error handling /start command",
            chat_id=chat_id,
            user_id_str=user_id_str,
            error=str(e),
            exc_info=True,
        )
        await telegram.send_message(
            chat_id,
            "Извините, произошла непредвиденная ошибка при обработке команды /start. Попробуйте позже.",
        )
