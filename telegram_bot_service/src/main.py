import asyncio
import datetime
import json

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

        logger.info("Processing message", message=message_text, telegram_id=telegram_id)

        # Get user data from REST service
        user = await rest.get_or_create_user(telegram_id, username)
        if not user:
            logger.error("Failed to get or create user", telegram_id=telegram_id)
            return

        user_id = user["id"]  # Get the internal user ID

        if message_text == "/start":
            await handle_start(telegram, rest, message_data.get("chat_id"), user)
        else:
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
                        "chat_id": message_data.get(
                            "chat_id"
                        ),  # Pass chat_id if needed by assistant
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
    """Handle single Telegram update."""
    try:
        message = update.get("message")
        if not message:
            return

        chat = message.get("chat", {})
        from_user = message.get("from", {})

        message_data = {
            "text": message.get("text"),
            "chat_id": chat.get("id"),  # Нужен только для handle_start
            "user_id": str(from_user.get("id")),
            "username": from_user.get("username"),
        }

        await process_message(telegram, rest, message_data)

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
