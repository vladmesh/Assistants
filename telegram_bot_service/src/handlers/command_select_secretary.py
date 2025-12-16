from typing import Any
from uuid import UUID

from shared_models import ServiceClientError, get_logger
from shared_models.api_schemas import TelegramUserRead

from clients.rest import TelegramRestClient
from clients.telegram import TelegramClient
from services import user_service

logger = get_logger(__name__)


async def handle_select_secretary(**context: Any) -> None:
    """Handles the callback query for selecting a secretary."""
    telegram: TelegramClient = context["telegram"]
    rest: TelegramRestClient = context["rest"]
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
            user = await user_service.get_user_by_telegram_id(rest, telegram_id)
            if not user:
                logger.warning(
                    "Callback query received but user not found",
                    telegram_id=telegram_id,
                )
                await telegram.answer_callback_query(
                    query_id,
                    text="Ошибка: Пользователь не найден. Попробуйте /start снова.",
                )
                return
        except ServiceClientError as e:
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
            await user_service.set_user_secretary(rest, user_id, secretary_id)

            # 4. Get assistant details to check for startup_message
            assistant_details = await rest.get_assistant_by_id(secretary_id)

            if assistant_details and assistant_details.startup_message:
                logger.info(
                    "Startup message found for assistant",
                    assistant_id=secretary_id,
                    startup_message=assistant_details.startup_message,
                )
                # 4.1. Create a fake user message
                await rest.create_message(
                    user_id=user_id,
                    assistant_id=secretary_id,
                    role="user",
                    content="привет",  # Standard greeting to initiate conversation flow
                    content_type="text",
                    status="processed",
                )
                logger.info(
                    "Fake user message created for startup",
                    user_id=user_id,
                    assistant_id=secretary_id,
                )

                # 4.2. Create the assistant's startup message
                await rest.create_message(
                    user_id=user_id,
                    assistant_id=secretary_id,
                    role="assistant",
                    content=assistant_details.startup_message,
                    content_type="text",
                    status="processed",
                )
                logger.info(
                    "Assistant startup message created in DB",
                    user_id=user_id,
                    assistant_id=secretary_id,
                )

                # 4.3. Send startup message to user and acknowledge callback
                await telegram.answer_callback_query(query_id)
                await telegram.send_message(chat_id, assistant_details.startup_message)
                logger.info(
                    "Startup message sent to user",
                    chat_id=chat_id,
                    assistant_id=secretary_id,
                )
            else:
                # 4.4. No startup message, send standard confirmation
                await telegram.answer_callback_query(
                    query_id
                )  # Acknowledge the button press
                confirmation_text = "Отлично! Секретарь назначен."
                await telegram.send_message(chat_id, confirmation_text)
                logger.info(
                    "Secretary assigned without startup message",
                    user_id=user_id,
                    secretary_id=secretary_id,
                )

        except ServiceClientError as e:
            logger.error(
                "REST Client Error setting user secretary during callback",
                user_id=str(user_id),
                secretary_id=str(secretary_id),
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
