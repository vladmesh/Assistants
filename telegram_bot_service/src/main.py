import asyncio
import datetime
import json
from typing import Any, Dict, List, Optional
from uuid import UUID

import aiohttp
import structlog
from client.rest import RestClient, RestClientError
from client.telegram import TelegramClient
from config.settings import settings
from handlers.start import handle_start
from pydantic import ValidationError  # Import ValidationError
from redis import asyncio as aioredis
from services.response_handler import handle_assistant_responses

# Import shared models
from shared_models.api_schemas import TelegramUserRead  # Import schema for type hint
from shared_models.queue import QueueMessage

logger = structlog.get_logger()


async def process_message(
    telegram: TelegramClient, rest: RestClient, message_data: dict
) -> None:
    """Process single message."""
    chat_id = message_data.get("chat_id")
    try:
        message_text = message_data.get("text")
        username = message_data.get("username")
        telegram_id_str = message_data.get("user_id")
        telegram_id = int(telegram_id_str)
        # chat_id defined earlier for error message sending

        logger.info("Processing message", message=message_text, telegram_id=telegram_id)

        if message_text == "/start":
            # Handle /start command - requires user object
            user: Optional[TelegramUserRead] = None
            try:
                user = await rest.get_or_create_user(telegram_id, username)
                # handle_start expects TelegramUserRead now
                await handle_start(telegram, rest, chat_id, user)
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
            except Exception as e:  # Catch other unexpected errors in handle_start
                logger.error(
                    "Unexpected error handling /start",
                    telegram_id=telegram_id,
                    error=str(e),
                    exc_info=True,
                )
                # handle_start already sends a generic error message
            return  # Stop processing after handling /start

        else:
            # Handle regular messages
            user: Optional[TelegramUserRead] = None
            try:
                user = await rest.get_user_by_telegram_id(telegram_id)
            except RestClientError as e:
                logger.error(
                    "REST Client Error getting user by telegram_id",
                    telegram_id=telegram_id,
                    error=str(e),
                )
                await telegram.send_message(
                    chat_id, "Не удалось проверить пользователя. Попробуйте позже."
                )
                return  # Stop processing

            if not user:
                # User does not exist (404 from REST client), prompt to /start
                logger.info(
                    "User does not exist, prompting /start", telegram_id=telegram_id
                )
                await telegram.send_message(
                    chat_id,
                    "Привет! Пожалуйста, используй команду /start, чтобы начать.",
                )
                return

            # User exists, check if secretary is assigned
            user_id = user.id  # Use attribute access
            assigned_secretary = None
            secretaries = []
            try:
                assigned_secretary = await rest.get_user_secretary(user_id)
            except RestClientError as e:
                logger.error(
                    "REST Client Error getting user secretary",
                    user_id=user_id,
                    error=str(e),
                )
                await telegram.send_message(
                    chat_id, "Не удалось проверить вашего секретаря. Попробуйте позже."
                )
                return  # Stop processing

            if not assigned_secretary:
                # Secretary not assigned (404 from REST client), prompt choice completion
                logger.info(
                    "User exists but no secretary assigned, prompting choice completion",
                    user_id=user_id,
                )
                try:
                    secretaries = await rest.list_secretaries()
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
                    return  # Stop processing

                if secretaries:
                    keyboard_buttons = []
                    for secretary in secretaries:
                        description = (
                            secretary.description or "(Нет описания)"
                        )  # Use attribute access
                        button_text = f"{secretary.name} - {description[:50]}{'...' if len(description) > 50 else ''}"  # Use attribute access
                        callback_data = (
                            f"select_secretary_{secretary.id}"  # Use attribute access
                        )
                        keyboard_buttons.append(
                            [{"text": button_text, "callback_data": callback_data}]
                        )

                    message_text = "Пожалуйста, заверши настройку, выбрав секретаря:"
                    await telegram.send_message_with_inline_keyboard(
                        chat_id=chat_id, text=message_text, keyboard=keyboard_buttons
                    )
                else:
                    # Fallback if secretaries list is empty (but request succeeded)
                    logger.warning(
                        "Secretaries list is empty, cannot re-prompt user",
                        user_id=user_id,
                    )
                    await telegram.send_message(
                        chat_id,
                        "Нет доступных секретарей для выбора. Попробуйте /start позже.",
                    )
                return  # Stop processing

            # User exists and secretary is assigned, proceed to send message to assistant
            logger.info(
                "User and secretary assignment confirmed, sending message to queue",
                user_id=user_id,
                secretary_id=assigned_secretary.id,  # Use attribute access
            )
            # Create simplified QueueMessage instance
            queue_message = QueueMessage(
                user_id=user_id,
                content=message_text,  # Directly use the message text string
                metadata={  # Add metadata directly to the QueueMessage
                    "username": username,
                    "telegram_id": telegram_id_str,
                    "chat_id": chat_id,
                    "source": "telegram",  # Explicitly set source here if needed elsewhere
                },
                # timestamp is handled by default_factory
            )

            # Send message to assistant queue
            redis = aioredis.from_url(settings.redis_url, **settings.redis_settings)
            await redis.lpush(
                settings.input_queue,
                queue_message.model_dump_json(),
            )
            logger.info(
                "Message sent to assistant queue", message=message_text, user_id=user_id
            )

    except RestClientError as e:  # Catch any REST client error not handled above
        logger.error(
            "Unhandled REST Client Error processing message",
            error=str(e),
            exc_info=True,
        )
        if chat_id:  # Ensure chat_id is available
            await telegram.send_message(
                chat_id,
                "Произошла внутренняя ошибка при обработке вашего запроса. Попробуйте позже.",
            )
    except (ValueError, TypeError) as e:  # Catch specific data processing errors
        logger.error(
            "Data error processing message",
            error=str(e),
            message_data=message_data,
            exc_info=True,
        )
        if chat_id:
            await telegram.send_message(
                chat_id, "Произошла ошибка при обработке данных вашего сообщения."
            )
    except Exception as e:  # Catch all other unexpected errors
        logger.error("Unexpected error processing message", error=str(e), exc_info=True)
        # Send generic error message if possible
        if chat_id:
            await telegram.send_message(
                chat_id,
                "Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже.",
            )


async def handle_telegram_update(
    telegram: TelegramClient, rest: RestClient, update: dict
) -> None:
    """Handle single Telegram update (message or callback query)."""
    chat_id = None  # Initialize chat_id
    try:
        if "message" in update:
            message = update["message"]
            chat = message.get("chat", {})
            from_user = message.get("from", {})
            chat_id = chat.get("id")  # Get chat_id

            message_data = {
                "text": message.get("text"),
                "chat_id": chat_id,
                "user_id": str(from_user.get("id")),
                "username": from_user.get("username"),
            }
            # process_message now handles its own exceptions and user messaging
            await process_message(telegram, rest, message_data)

        elif "callback_query" in update:
            callback_query = update["callback_query"]
            query_id = callback_query["id"]
            from_user = callback_query["from"]
            message = callback_query.get("message", {})  # Get message safely
            chat = message.get("chat", {})
            chat_id = chat.get("id")  # Get chat_id
            data = callback_query["data"]

            telegram_id = from_user["id"]
            # username = from_user.get("username") # Not needed directly here

            logger.info(
                "Processing callback query",
                query_id=query_id,
                data=data,
                telegram_id=telegram_id,
            )

            if data.startswith("select_secretary_"):
                secretary_id_str = data.split("_")[-1]
                user: Optional[TelegramUserRead] = None
                try:
                    secretary_id = UUID(secretary_id_str)
                    # Get internal user ID
                    user = await rest.get_user_by_telegram_id(telegram_id)

                    if not user:
                        # User not found (404)
                        logger.warning(
                            "Callback query received but user not found (404)",
                            telegram_id=telegram_id,
                        )
                        await telegram.answer_callback_query(
                            query_id,
                            text="Ошибка: Пользователь не найден. Попробуйте /start снова.",
                        )
                        return

                    user_id = user.id

                    # Assign secretary via REST
                    # This will raise RestClientError on failure (non-404)
                    assignment_result = await rest.set_user_secretary(
                        user_id, secretary_id
                    )

                    # If no exception, assignment succeeded
                    await telegram.answer_callback_query(query_id)
                    confirmation_text = "Отлично! Секретарь назначен."
                    if chat_id:  # Ensure chat_id is available
                        await telegram.send_message(chat_id, confirmation_text)
                    logger.info(
                        "Secretary assigned successfully via callback",
                        user_id=user_id,
                        secretary_id=secretary_id,
                    )

                except RestClientError as e:
                    # Handle errors from get_user_by_telegram_id or set_user_secretary
                    logger.error(
                        "REST Client Error processing callback",
                        telegram_id=telegram_id,
                        data=data,
                        error=str(e),
                    )
                    await telegram.answer_callback_query(
                        query_id, text="Ошибка связи с сервером. Попробуйте позже."
                    )
                except (ValueError, KeyError, IndexError) as e:
                    logger.error(
                        "Error processing callback query data", data=data, error=str(e)
                    )
                    await telegram.answer_callback_query(
                        query_id, text="Ошибка обработки данных."
                    )
                except Exception as e:  # Catch other unexpected errors
                    logger.error(
                        "Unexpected error processing callback",
                        telegram_id=telegram_id,
                        data=data,
                        error=str(e),
                        exc_info=True,
                    )
                    await telegram.answer_callback_query(
                        query_id, text="Произошла непредвиденная ошибка."
                    )
            else:
                # Handle other callback queries if any in the future
                logger.warning("Received unhandled callback query", data=data)
                await telegram.answer_callback_query(query_id)
        else:
            pass

    except Exception as e:
        # Catch-all for errors before chat_id might be extracted or other broad issues
        logger.error(
            "Critical error handling Telegram update", error=str(e), exc_info=True
        )
        # Attempt to notify user if possible (though chat_id might be None)
        if chat_id:
            try:
                await telegram.send_message(
                    chat_id,
                    "Произошла критическая ошибка при обработке вашего запроса.",
                )
            except Exception as send_e:
                logger.error(
                    "Failed to send critical error message to user",
                    chat_id=chat_id,
                    send_error=str(send_e),
                )


async def main():
    """Main function."""
    logger.info("Starting bot")

    # Initialize Redis
    redis = aioredis.from_url(settings.redis_url, **settings.redis_settings)
    logger.info("Connected to Redis", url=settings.redis_url)

    # Initialize clients
    async with TelegramClient() as telegram, RestClient() as rest:
        logger.info("Initialized clients")

        # Start response handler
        response_handler = asyncio.create_task(
            handle_assistant_responses(telegram, redis)
        )
        logger.info("Started response handler task")

        try:
            # Store last update id
            last_update_id = 0

            while True:
                try:
                    # Get updates from Telegram
                    updates = await telegram.get_updates(offset=last_update_id + 1)

                    for update in updates:
                        # Process update
                        await handle_telegram_update(telegram, rest, update)
                        # Update last_update_id
                        last_update_id = max(last_update_id, update.get("update_id", 0))

                    # Small delay to prevent tight loop
                    await asyncio.sleep(settings.update_interval)

                except Exception as e:
                    logger.error("Error in main loop", error=str(e), exc_info=True)
                    await asyncio.sleep(settings.update_interval)

        except asyncio.CancelledError:
            logger.info("Bot shutdown requested")
        except Exception as e:
            logger.error("Critical error in main loop", error=str(e), exc_info=True)
        finally:
            # Cancel response handler
            response_handler.cancel()
            try:
                await response_handler
            except asyncio.CancelledError:
                pass
            logger.info("Response handler stopped")


if __name__ == "__main__":
    asyncio.run(main())
