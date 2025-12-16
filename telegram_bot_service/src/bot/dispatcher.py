from typing import Any

from shared_models import get_logger

from clients.rest import TelegramRestClient
from clients.telegram import TelegramClient
from handlers import (
    callback_query,
    command_select_secretary,
    command_start,
    message_text,
)

logger = get_logger(__name__)


async def dispatch_update(
    update: dict[str, Any], telegram: TelegramClient, rest: TelegramRestClient
) -> None:
    """Determines the type of update and calls the appropriate handler."""
    try:
        if "message" in update:
            message = update["message"]
            chat = message.get("chat", {})
            from_user = message.get("from", {})
            chat_id = chat.get("id")
            user_id_str = str(from_user.get("id"))
            username = from_user.get("username")
            text = message.get("text")

            if not chat_id or not user_id_str:
                logger.warning(
                    "Received message without chat_id or user_id", update=update
                )
                return

            # Создаем контекстный словарь для передачи в хэндлер
            context = {
                "telegram": telegram,
                "rest": rest,
                "update": update,
                "message": message,
                "chat_id": chat_id,
                "user_id_str": user_id_str,
                "username": username,
                "text": text,
            }

            if text == "/start":
                logger.info(
                    "Dispatching to handle_start", chat_id=chat_id, user_id=user_id_str
                )
                await command_start.handle_start(**context)
            elif text:
                logger.info(
                    "Dispatching to handle_text_message",
                    chat_id=chat_id,
                    user_id=user_id_str,
                )
                await message_text.handle_text_message(**context)
            else:
                # Обрабатываем медиа/документы позже, сейчас пропускаем
                logger.debug(
                    "Received non-text message, skipping",
                    chat_id=chat_id,
                    user_id=user_id_str,
                )

        elif "callback_query" in update:
            callback = update["callback_query"]
            query_id = callback["id"]
            from_user = callback["from"]
            message = callback.get(
                "message", {}
            )  # Сообщение, к которому привязана кнопка
            chat = message.get("chat", {})
            chat_id = chat.get("id")
            user_id_str = str(from_user.get("id"))
            username = from_user.get("username")
            data = callback.get("data")

            if not chat_id or not user_id_str or not query_id or not data:
                logger.warning(
                    "Received callback_query with missing data", update=update
                )
                # Попытаться ответить на колбэк, если есть ID
                if query_id:
                    try:
                        await telegram.answer_callback_query(
                            query_id, text="Ошибка обработки данных."
                        )
                    except Exception as e_ans:
                        logger.error(
                            "Failed to answer callback query on error",
                            query_id=query_id,
                            error=str(e_ans),
                        )
                return

            # Создаем контекстный словарь
            context = {
                "telegram": telegram,
                "rest": rest,
                "update": update,
                "callback": callback,
                "query_id": query_id,
                "chat_id": chat_id,
                "user_id_str": user_id_str,
                "username": username,
                "data": data,
                "message": message,  # Передаем исходное сообщение тоже
            }

            if data.startswith("select_secretary_"):
                logger.info(
                    "Dispatching to handle_select_secretary",
                    chat_id=chat_id,
                    user_id=user_id_str,
                    data=data,
                )
                await command_select_secretary.handle_select_secretary(**context)
            else:
                # Другие колбэки
                logger.info(
                    "Dispatching to handle_callback_query",
                    chat_id=chat_id,
                    user_id=user_id_str,
                    data=data,
                )
                await callback_query.handle_callback_query(**context)

        else:
            logger.warning(
                "Received unknown update type", update_id=update.get("update_id")
            )

    except Exception as e:
        logger.error(
            "Error during dispatching update",
            error=str(e),
            update=update,
            exc_info=True,
        )
        # Попытка уведомить пользователя об ошибке, если возможно
        chat_id = None
        if "message" in update:
            chat_id = update.get("message", {}).get("chat", {}).get("id")
        elif "callback_query" in update:
            chat_id = (
                update.get("callback_query", {})
                .get("message", {})
                .get("chat", {})
                .get("id")
            )

        if chat_id:
            try:
                await telegram.send_message(
                    chat_id, "Произошла внутренняя ошибка при обработке вашего запроса."
                )
            except Exception as send_e:
                logger.error(
                    "Failed to send error message to user after dispatch error",
                    chat_id=chat_id,
                    error=str(send_e),
                )
