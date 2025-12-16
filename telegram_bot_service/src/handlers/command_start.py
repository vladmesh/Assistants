from typing import Any

from shared_models import ServiceClientError, get_logger
from shared_models.api_schemas import TelegramUserRead

from clients.rest import TelegramRestClient
from clients.telegram import TelegramClient
from services import user_service

logger = get_logger(__name__)


async def handle_start(**context: Any) -> None:
    """Handles the /start command.

    - Gets or creates the user via REST.
    - Lists available secretaries.
    - Prompts the user to choose a secretary via inline keyboard.
    """
    telegram: TelegramClient = context["telegram"]
    rest: TelegramRestClient = context["rest"]
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
        except ServiceClientError as e:
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

        # 2. Prompt user to select secretary using the new service function
        prompt = "👋 Привет! Пожалуйста, выбери своего секретаря:"
        success = await user_service.prompt_secretary_selection(
            telegram=telegram,
            rest=rest,
            chat_id=chat_id,
            prompt_message=prompt,
            user_id_for_log=user_id,  # Pass user UUID for logging
        )

        if success:
            logger.info(
                "Secretary selection prompt initiated successfully for /start",
                user_id=user_id,
            )
        # else: The prompt function already logs errors and notifies the user

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
            (
                "Извините, произошла непредвиденная ошибка при обработке команды "
                "/start. Попробуйте позже."
            ),
        )
