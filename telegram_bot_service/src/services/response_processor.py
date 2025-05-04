import asyncio
import json

import structlog
from clients.rest import RestClient
from clients.telegram import TelegramClient
from config.settings import settings
from pydantic import ValidationError
from redis import asyncio as aioredis

from shared_models.queue import AssistantResponseMessage

logger = structlog.get_logger()


async def handle_assistant_responses(
    telegram: TelegramClient, redis: aioredis.Redis
) -> None:
    """
    Handle responses from assistant.

    Args:
        telegram: Telegram client instance
        redis: Redis client instance
    """
    logger.info("Started assistant response handler")

    async with RestClient() as rest:
        while True:
            try:
                # Get response from assistant queue
                response = await redis.brpop(settings.assistant_output_queue, timeout=1)

                if response:
                    _, data = response
                    try:
                        # Validate and parse incoming message using Pydantic model
                        response_message = AssistantResponseMessage.model_validate_json(
                            data
                        )
                        logger.debug(
                            "Successfully validated AssistantResponseMessage",
                            user_id=response_message.user_id,
                        )
                    except ValidationError as e:
                        logger.error(
                            "Failed to validate incoming assistant response message from queue",
                            raw_data=data.decode("utf-8", errors="ignore"),
                            errors=e.errors(),
                            exc_info=True,
                        )
                        continue  # Skip processing this invalid message

                    # Get user data from REST service using validated user_id
                    user_id = response_message.user_id
                    # RestClient returns TelegramUserRead or None
                    user = await rest.get_user_by_id(user_id)  # user_id is already int
                    if not user:
                        logger.error("User not found", user_id=user_id)
                        continue

                    # Use attribute access for the Pydantic model
                    chat_id = user.telegram_id
                    if not chat_id:
                        # This should not happen if user object is valid, but keep check
                        logger.error(
                            "No telegram_id in user data object", user_id=user_id
                        )
                        continue

                    # Check response status using model attribute
                    if response_message.status == "error":
                        error_message = (
                            response_message.error or "Произошла неизвестная ошибка"
                        )
                        logger.error(
                            "Error received in assistant response",
                            error=error_message,
                            user_id=user_id,
                            source=response_message.source,
                        )
                        # Send error message to user
                        await telegram.send_message(
                            chat_id=chat_id,
                            text=f"Извините, произошла ошибка: {error_message}",
                        )
                    else:
                        # Send successful response to user using model attribute
                        response_text = response_message.response
                        if response_text:
                            await telegram.send_message(
                                chat_id=chat_id,
                                text=response_text,
                                parse_mode="Markdown",
                            )

                            logger.info(
                                "Sent successful response to user",
                                user_id=user_id,
                                message_preview=response_text[:100],
                                source=response_message.source,
                            )
                        else:
                            logger.warning(
                                "Empty successful response from assistant",
                                user_id=user_id,
                                source=response_message.source,
                            )

            except json.JSONDecodeError as e:  # Should be caught by ValidationError now
                logger.error(
                    "Invalid JSON in response (should be caught by validation)",
                    error=str(e),
                )
            except KeyError as e:  # Should be caught by ValidationError now
                logger.error(
                    "Missing required field in response (should be caught by validation)",
                    error=str(e),
                )
            except Exception as e:
                logger.error("Error handling assistant response", error=str(e))

            # Small delay to prevent tight loop
            await asyncio.sleep(0.1)
