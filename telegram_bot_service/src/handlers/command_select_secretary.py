from typing import Any
from uuid import UUID

import structlog

# Обрати внимание: пути импорта изменились на clients
from clients.rest import RestClient, RestClientError
from clients.telegram import TelegramClient

# Используем user_service
from services import user_service

# Import shared models if needed for type hints
from shared_models.api_schemas import TelegramUserRead

logger = structlog.get_logger()


async def handle_select_secretary(**context: Any) -> None:
    """Handles the callback query for selecting a secretary."""
    telegram: TelegramClient = context["telegram"]
    rest: RestClient = context["rest"]
    query_id: str = context["query_id"]
    chat_id: int = context["chat_id"]
    user_id_str: str = context["user_id_str"]
    data: str = context["data"]

    logger.info(
        "Handling select_secretary callback",
        query_id=query_id,
        data=data,
        chat_id=chat_id,
        user_id_str=user_id_str,
    )

    try:
        # 1. Parse secretary_id from data
        try:
            secretary_id_str = data.split("select_secretary_")[1]
            secretary_id = UUID(secretary_id_str)
        except (IndexError, ValueError) as e:
            logger.error(
                "Failed to parse secretary_id from callback data",
                data=data,
                error=str(e),
            )
            await telegram.answer_callback_query(
                query_id, text="Ошибка: Неверный формат данных."
            )
            return

        # 2. Get internal user ID
        user: TelegramUserRead | None = None
        telegram_id = int(user_id_str)  # Convert here, handle ValueError below
        try:
            # Вызов user_service
            user = await user_service.get_user_by_telegram_id(rest, telegram_id)
            if not user:
                # User not found (404), maybe started conversation elsewhere?
                logger.warning(
                    "Callback query received but user not found",
                    telegram_id=telegram_id,
                )
                await telegram.answer_callback_query(
                    query_id,
                    text="Ошибка: Пользователь не найден. Попробуйте /start снова.",
                )
                return
        except RestClientError as e:
            logger.error(
                "REST Client Error getting user by telegram_id during callback",
                telegram_id=telegram_id,
                error=str(e),
            )
            await telegram.answer_callback_query(
                query_id, text="Ошибка связи с сервером. Попробуйте позже."
            )
            return
        except ValueError:
            logger.error(
                "Invalid telegram_id format in callback", user_id_str=user_id_str
            )
            await telegram.answer_callback_query(
                query_id, text="Ошибка: Неверный формат ID."
            )
            return

        user_id = user.id

        # 3. Assign secretary via REST
        try:
            # Assuming set_user_secretary returns the updated user or confirms assignment
            # Вызов user_service
            await user_service.set_user_secretary(rest, user_id, secretary_id)

            # 4. Confirm success to user
            await telegram.answer_callback_query(
                query_id
            )  # Acknowledge the button press
            confirmation_text = "Отлично! Секретарь назначен."
            await telegram.send_message(chat_id, confirmation_text)
            logger.info(
                "Secretary assigned successfully via callback",
                user_id=user_id,
                secretary_id=secretary_id,
            )

        except RestClientError as e:
            logger.error(
                "REST Client Error setting user secretary during callback",
                user_id=user_id,
                secretary_id=secretary_id,
                error=str(e),
            )
            await telegram.answer_callback_query(
                query_id, text="Ошибка при назначении секретаря. Попробуйте позже."
            )
            return

    except Exception as e:
        logger.error(
            "Unexpected error handling select_secretary callback",
            query_id=query_id,
            data=data,
            error=str(e),
            exc_info=True,
        )
        # Send generic error answer to callback
        try:
            await telegram.answer_callback_query(
                query_id, text="Произошла непредвиденная ошибка."
            )
        except Exception as e_ans:
            logger.error(
                "Failed to answer callback query on unexpected error",
                query_id=query_id,
                error=str(e_ans),
            )
