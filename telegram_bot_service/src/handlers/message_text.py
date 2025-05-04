from typing import Any, List

import structlog

# Обрати внимание: пути импорта изменились на clients
from clients.rest import RestClient, RestClientError
from clients.telegram import TelegramClient

# Импортируем фабрику клавиатур (уже используется в command_start)
from keyboards.secretary_selection import create_secretary_selection_keyboard

# Используем user_service
from services import message_queue, user_service

# Import shared models
from shared_models.api_schemas import AssistantRead, TelegramUserRead

logger = structlog.get_logger()


async def handle_text_message(**context: Any) -> None:
    """Handles regular text messages from users.

    - Checks if the user exists.
    - Checks if a secretary is assigned.
    - Prompts for secretary selection if needed.
    - Sends the message to the assistant queue if user and secretary are set.
    """
    telegram: TelegramClient = context["telegram"]
    rest: RestClient = context["rest"]
    chat_id: int = context["chat_id"]
    user_id_str: str = context["user_id_str"]
    username: str | None = context["username"]
    text: str | None = context["text"]  # Text should exist based on dispatcher logic

    if not text:  # Should ideally not happen if dispatched here
        logger.warning("handle_text_message called without text", **context)
        return

    try:
        telegram_id = int(user_id_str)
        logger.info(
            "Handling text message",
            chat_id=chat_id,
            telegram_id=telegram_id,
            text_preview=text[:50],
        )

        # 1. Check if user exists
        user: TelegramUserRead | None = None
        try:
            # Вызов user_service
            user = await user_service.get_user_by_telegram_id(rest, telegram_id)
        except RestClientError as e:
            # Handle non-404 errors specifically if needed, otherwise generic message
            logger.error(
                "REST Client Error getting user by telegram_id",
                telegram_id=telegram_id,
                error=str(e),
            )
            await telegram.send_message(
                chat_id, "Не удалось проверить пользователя. Попробуйте позже."
            )
            return
        except ValueError:
            logger.error("Invalid telegram_id format", user_id_str=user_id_str)
            await telegram.send_message(
                chat_id, "Произошла ошибка: неверный формат ID."
            )
            return

        if not user:
            # User does not exist (404 from REST client), prompt to /start
            logger.info(
                "User does not exist, prompting /start", telegram_id=telegram_id
            )
            await telegram.send_message(
                chat_id, "Привет! Пожалуйста, используй команду /start, чтобы начать."
            )
            return

        # User exists, get internal ID
        user_id = user.id

        # 2. Check if secretary is assigned
        assigned_secretary: AssistantRead | None = None
        try:
            # Вызов user_service
            assigned_secretary = await user_service.get_assigned_secretary(
                rest, user_id
            )
        except RestClientError as e:
            # Handle non-404 errors specifically if needed
            logger.error(
                "REST Client Error getting user secretary",
                user_id=user_id,
                error=str(e),
            )
            await telegram.send_message(
                chat_id, "Не удалось проверить вашего секретаря. Попробуйте позже."
            )
            return

        if not assigned_secretary:
            # Secretary not assigned (404 from REST client), prompt choice completion
            logger.info(
                "User exists but no secretary assigned, prompting choice",
                user_id=user_id,
            )
            secretaries: List[AssistantRead] = []
            try:
                # Вызов user_service
                secretaries = await user_service.list_available_secretaries(rest)
            except RestClientError as e:
                logger.error(
                    "REST Client Error listing secretaries for re-prompt",
                    user_id=user_id,
                    error=str(e),
                )
                await telegram.send_message(
                    chat_id,
                    "Не удалось загрузить список секретарей. Попробуйте /start позже.",
                )
                return

            if secretaries:
                keyboard_buttons = create_secretary_selection_keyboard(secretaries)
                message_text = (
                    "Похоже, у тебя еще не выбран секретарь. Пожалуйста, выбери одного:"
                )
                await telegram.send_message_with_inline_keyboard(
                    chat_id=chat_id, text=message_text, keyboard=keyboard_buttons
                )
            else:
                logger.warning(
                    "Secretaries list is empty, cannot re-prompt user", user_id=user_id
                )
                await telegram.send_message(
                    chat_id,
                    "Нет доступных секретарей для выбора. Попробуйте /start позже.",
                )
            return  # Stop processing the original message

        # 3. User exists and secretary is assigned, send message to queue
        logger.info(
            "User and secretary confirmed, sending message to queue",
            user_id=user_id,
            secretary_id=assigned_secretary.id,
        )

        # Prepare metadata for the queue message
        metadata = {
            "username": username,
            "telegram_id": user_id_str,
            "chat_id": chat_id,
            # source will be added by message_queue service if needed
        }

        # --- Use message_queue service ---
        try:
            await message_queue.send_message_to_assistant(
                user_id=user_id, content=text, metadata=metadata
            )
            # Optionally send confirmation to user?
            # await telegram.send_message(chat_id, "Сообщение передано ассистенту.")
        except (
            Exception
        ) as e_queue:  # Catch RedisError or other exceptions from the service
            logger.error(
                "Failed to send message via message_queue service",
                user_id=user_id,
                error=str(e_queue),
                exc_info=True,
            )
            await telegram.send_message(
                chat_id, "Не удалось передать сообщение ассистенту. Попробуйте позже."
            )
        # --- End message_queue service usage ---

    except Exception as e:
        logger.error(
            "Unexpected error handling text message",
            chat_id=chat_id,
            user_id_str=user_id_str,
            error=str(e),
            exc_info=True,
        )
        # Send generic error message
        await telegram.send_message(
            chat_id, "Произошла непредвиденная ошибка при обработке вашего сообщения."
        )
