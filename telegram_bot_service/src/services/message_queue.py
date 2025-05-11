from typing import Any, Dict
from uuid import UUID

import redis.asyncio as aioredis
import structlog
from config.settings import settings

from shared_models.queue import QueueMessage

logger = structlog.get_logger()


async def send_message_to_assistant(
    user_id: UUID, content: str, metadata: Dict[str, Any]
) -> None:
    """Formats a message and sends it to the assistant's input queue via Redis.

    Args:
        user_id: The internal UUID of the user.
        content: The text content of the message.
        metadata: Additional metadata (chat_id, username, etc.).

    Raises:
        RedisError: If connection or command fails.
        Exception: For other unexpected errors during message formatting or sending.
    """
    logger.debug("Preparing message for assistant queue", user_id=user_id)

    try:
        # Create QueueMessage instance
        # Ensure metadata includes essential info if not already present
        metadata["source"] = metadata.get("source", "telegram")  # Ensure source is set
        queue_message = QueueMessage(
            user_id=user_id,
            content=content,
            metadata=metadata,
        )

        message_json = queue_message.model_dump_json()

    except Exception as e:
        logger.error(
            "Failed to create or serialize QueueMessage",
            user_id=user_id,
            error=str(e),
            exc_info=True,
        )
        # Re-raise or handle appropriately - re-raising for now
        raise

    redis_client = None
    try:
        # Consider using a shared Redis client instance if performance becomes an issue
        # For now, create/close connection per message for simplicity
        redis_client = aioredis.from_url(settings.redis_url, **settings.redis_settings)
        await redis_client.lpush(settings.input_queue, message_json)
        logger.info(
            "Message successfully sent to assistant queue",
            user_id=user_id,
            queue=settings.input_queue,
            message_preview=content[:50],
        )
    except aioredis.RedisError as e:
        logger.error(
            "Redis error sending message to assistant queue",
            user_id=user_id,
            queue=settings.input_queue,
            error=str(e),
            exc_info=True,
        )
        # Re-raise Redis specific error to be potentially handled by caller
        raise
    except Exception as e:
        logger.error(
            "Unexpected error sending message to Redis",
            user_id=user_id,
            error=str(e),
            exc_info=True,
        )
        raise  # Re-raise other exceptions
    finally:
        if redis_client:
            try:
                await redis_client.close()
                logger.debug(
                    "Redis client connection closed for message queue service."
                )
            except Exception as e_close:
                logger.error(
                    "Failed to close Redis connection in message queue service",
                    error=str(e_close),
                )
