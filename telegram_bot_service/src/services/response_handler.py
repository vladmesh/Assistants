import asyncio
import json

import structlog
from client.rest import RestClient
from client.telegram import TelegramClient
from config.settings import settings
from redis import asyncio as aioredis

logger = structlog.get_logger()


async def handle_assistant_responses(telegram: TelegramClient) -> None:
    """
    Handle responses from assistant.

    Args:
        telegram: Telegram client instance
    """
    redis = aioredis.from_url(settings.redis_url, **settings.redis_settings)
    logger.info("Started assistant response handler")

    async with RestClient() as rest:
        while True:
            try:
                # Get response from assistant queue
                response = await redis.brpop(settings.assistant_output_queue, timeout=1)

                if response:
                    _, data = response
                    response_data = json.loads(data)

                    # Get user data from REST service
                    user_id = response_data.get("user_id")
                    if not user_id:
                        logger.error("No user_id in response data")
                        continue

                    user = await rest.get_user_by_id(int(user_id))
                    if not user:
                        logger.error("User not found", user_id=user_id)
                        continue

                    chat_id = user.get(
                        "telegram_id"
                    )  # telegram_id is the same as chat_id
                    if not chat_id:
                        logger.error("No telegram_id in user data", user_id=user_id)
                        continue

                    # Check response status
                    if response_data.get("status") == "error":
                        error_message = response_data.get(
                            "error", "Произошла неизвестная ошибка"
                        )
                        logger.error(
                            "Error in assistant response",
                            error=error_message,
                            user_id=user_id,
                        )
                        # Send error message to user
                        await telegram.send_message(
                            chat_id=chat_id,
                            text=f"Извините, произошла ошибка: {error_message}",
                        )
                    else:
                        # Send successful response to user
                        response_text = response_data.get("response")
                        if response_text:
                            await telegram.send_message(
                                chat_id=chat_id, text=response_text
                            )

                            logger.info(
                                "Sent response to user",
                                user_id=user_id,
                                message_preview=response_text[:100],
                            )
                        else:
                            logger.warning(
                                "Empty response from assistant", user_id=user_id
                            )

            except json.JSONDecodeError as e:
                logger.error("Invalid JSON in response", error=str(e))
            except KeyError as e:
                logger.error("Missing required field in response", error=str(e))
            except Exception as e:
                logger.error("Error handling assistant response", error=str(e))

            # Small delay to prevent tight loop
            await asyncio.sleep(0.1)
