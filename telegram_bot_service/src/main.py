import asyncio
import datetime
import json
from uuid import UUID

import aiohttp
import structlog
from client.rest import RestClient
from client.telegram import TelegramClient
from config.settings import settings
from handlers.start import handle_start
from pydantic import ValidationError  # Import ValidationError
from redis import asyncio as aioredis
from services.response_handler import handle_assistant_responses

# Import shared models
from shared_models.queue import (
    HumanQueueMessageContent,
    QueueMessage,
    QueueMessageSource,
    QueueMessageType,
)

logger = structlog.get_logger()


async def process_message(
    telegram: TelegramClient, rest: RestClient, message_data: dict
) -> None:
    """Process single message."""
    try:
        message_text = message_data.get("text")
        username = message_data.get("username")
        telegram_id_str = message_data.get("user_id")
        telegram_id = int(telegram_id_str)
        chat_id = message_data.get("chat_id")  # Get chat_id for sending messages

        logger.info("Processing message", message=message_text, telegram_id=telegram_id)

        if message_text == "/start":
            # Get or create user first for /start command
            user = await rest.get_or_create_user(telegram_id, username)
            if not user:
                logger.error(
                    "Failed to get or create user for /start", telegram_id=telegram_id
                )
                await telegram.send_message(
                    chat_id, "Произошла ошибка. Попробуйте позже."
                )
                return
            await handle_start(telegram, rest, chat_id, user)
        else:
            # Check if user exists for non-/start messages
            user = await rest.get_user_by_telegram_id(telegram_id)
            if not user:
                # User does not exist, prompt to /start
                logger.info(
                    "User does not exist, prompting /start", telegram_id=telegram_id
                )
                await telegram.send_message(
                    chat_id,
                    "Привет! Пожалуйста, используй команду /start, чтобы начать.",
                )
                return

            # User exists, check if secretary is assigned
            user_id = user["id"]  # Get the internal user ID
            assigned_secretary = await rest.get_user_secretary(user_id)
            if not assigned_secretary:
                logger.info(
                    "User exists but no secretary assigned, prompting choice completion",
                    user_id=user_id,
                )
                # Re-send the secretary selection prompt with keyboard
                secretaries = await rest.list_secretaries()
                if secretaries:
                    keyboard_buttons = []
                    for secretary in secretaries:
                        description = secretary.get("description") or "(Нет описания)"
                        button_text = f"{secretary.get('name')} - {description[:50]}{'...' if len(description) > 50 else ''}"
                        callback_data = f"select_secretary_{secretary.get('id')}"
                        keyboard_buttons.append(
                            [{"text": button_text, "callback_data": callback_data}]
                        )

                    message_text = "Пожалуйста, заверши настройку, выбрав секретаря:"
                    await telegram.send_message_with_inline_keyboard(
                        chat_id=chat_id, text=message_text, keyboard=keyboard_buttons
                    )
                else:
                    # Fallback if secretaries couldn't be fetched again
                    logger.error(
                        "Could not fetch secretaries to re-prompt user", user_id=user_id
                    )
                    await telegram.send_message(
                        chat_id,
                        "Пожалуйста, используй команду /start для выбора секретаря.",
                    )
                return

            # User exists and secretary is assigned, proceed to send message to assistant
            logger.info(
                "User and secretary assignment confirmed, sending message to queue",
                user_id=user_id,
                secretary_id=assigned_secretary.get("id"),
            )
            # Create QueueMessage instance
            queue_message = QueueMessage(
                user_id=user_id,
                source=QueueMessageSource.TELEGRAM,  # Use Enum value
                type=QueueMessageType.HUMAN,  # Use Enum value
                content=HumanQueueMessageContent(
                    message=message_text,
                    metadata={
                        "username": username,
                        "telegram_id": telegram_id_str,  # Keep as string if needed elsewhere, or convert user["telegram_id"] if available
                        "chat_id": chat_id,  # Pass chat_id if needed by assistant
                    },
                ),
                # timestamp is handled by default factory in QueueMessage
            )

            # Send message to assistant queue
            redis = aioredis.from_url(settings.redis_url, **settings.redis_settings)
            await redis.lpush(
                settings.input_queue,
                queue_message.model_dump_json(),  # Serialize using Pydantic model method
            )
            logger.info(
                "Message sent to assistant queue", message=message_text, user_id=user_id
            )

    except (
        aiohttp.ClientError,
        json.JSONDecodeError,
        ValueError,
        ValidationError,
    ) as e:
        logger.error(
            "Error processing message (client/data related)",
            error=str(e),
            exc_info=True,
        )
    except Exception as e:
        logger.error("Error processing message", error=str(e), exc_info=True)


async def handle_telegram_update(
    telegram: TelegramClient, rest: RestClient, update: dict
) -> None:
    """Handle single Telegram update (message or callback query)."""
    try:
        if "message" in update:
            message = update["message"]
            chat = message.get("chat", {})
            from_user = message.get("from", {})

            message_data = {
                "text": message.get("text"),
                "chat_id": chat.get("id"),
                "user_id": str(from_user.get("id")),
                "username": from_user.get("username"),
            }
            await process_message(telegram, rest, message_data)

        elif "callback_query" in update:
            callback_query = update["callback_query"]
            query_id = callback_query["id"]
            from_user = callback_query["from"]
            chat = callback_query["message"]["chat"]
            data = callback_query["data"]

            telegram_id = from_user["id"]
            chat_id = chat["id"]
            username = from_user.get("username")  # For get_or_create_user if needed

            logger.info(
                "Processing callback query",
                query_id=query_id,
                data=data,
                telegram_id=telegram_id,
            )

            if data.startswith("select_secretary_"):
                secretary_id_str = data.split("_")[-1]
                try:
                    secretary_id = UUID(secretary_id_str)
                    # Get internal user ID - crucial!
                    # We might need get_or_create here if user somehow clicks button before /start fully processed?
                    # Safer approach: ensure user exists first.
                    user = await rest.get_user_by_telegram_id(telegram_id)
                    if not user:
                        # Should not happen if /start flow is correct, but handle defensively
                        logger.warning(
                            "Callback query received but user not found",
                            telegram_id=telegram_id,
                        )
                        await telegram.answer_callback_query(
                            query_id,
                            text="Ошибка: Пользователь не найден. Попробуйте /start снова.",
                        )
                        return

                    user_id = user["id"]

                    # Assign secretary via REST
                    assignment_result = await rest.set_user_secretary(
                        user_id, secretary_id
                    )

                    if assignment_result:
                        await telegram.answer_callback_query(query_id)
                        confirmation_text = "Отлично! Секретарь назначен."
                        await telegram.send_message(chat_id, confirmation_text)
                        logger.info(
                            "Secretary assigned successfully via callback",
                            user_id=user_id,
                            secretary_id=secretary_id,
                        )

                    else:
                        await telegram.answer_callback_query(
                            query_id, text="Ошибка при назначении секретаря."
                        )
                        logger.error(
                            "Failed to assign secretary via REST",
                            user_id=user_id,
                            secretary_id=secretary_id,
                        )

                except (ValueError, KeyError, IndexError) as e:
                    logger.error(
                        "Error processing callback query data", data=data, error=str(e)
                    )
                    await telegram.answer_callback_query(
                        query_id, text="Ошибка обработки данных."
                    )
            else:
                # Handle other callback queries if any in the future
                logger.warning("Received unhandled callback query", data=data)
                await telegram.answer_callback_query(query_id)
        else:
            logger.debug("Received update type not handled", update_keys=update.keys())

    except (KeyError, TypeError) as e:
        logger.warning(
            f"Error parsing Telegram update: {e}", update_preview=str(update)[:100]
        )
    except Exception as e:
        logger.error("Error handling update", error=str(e), exc_info=True)


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
