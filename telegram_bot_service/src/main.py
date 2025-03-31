import asyncio
import json

import structlog
from client.rest import RestClient
from client.telegram import TelegramClient
from config.settings import settings
from handlers.start import handle_start
from redis import asyncio as aioredis
from services.response_handler import handle_assistant_responses

logger = structlog.get_logger()


async def process_message(
    telegram: TelegramClient, rest: RestClient, message_data: dict
) -> None:
    """Process single message."""
    try:
        message = message_data.get("text")
        username = message_data.get("username")
        telegram_id = message_data.get("user_id")

        logger.info("Processing message", message=message, telegram_id=telegram_id)

        # Get user data from REST service
        user = await rest.get_or_create_user(int(telegram_id), username)
        if not user:
            logger.error("Failed to get or create user", telegram_id=telegram_id)
            return

        if message == "/start":
            await handle_start(telegram, rest, message_data.get("chat_id"), user)
        else:
            # Send message to assistant queue
            redis = aioredis.from_url(settings.redis_url, **settings.redis_settings)
            await redis.lpush(
                settings.input_queue,
                json.dumps(
                    {"user_id": user["id"], "text": message, "username": username}
                ),
            )
            logger.info("Message sent to assistant queue", message=message)

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
