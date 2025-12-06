from typing import Any

import redis.asyncio as redis
import structlog

# Import new models and remove old ones
# from shared_models import HumanQueueMessage, QueueMessageSource, ToolQueueMessage
from shared_models import QueueMessageSource, QueueTrigger, TriggerType

from config.settings import Settings

logger = structlog.get_logger()


class RedisService:
    """Service for working with Redis"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.redis: redis.Redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=False,  # Keep False for sending JSON bytes
        )

    async def send_to_assistant(
        self,
        user_id: int,
        trigger_type: TriggerType,
        payload: dict[str, Any] | None = None,
        source: QueueMessageSource = QueueMessageSource.CALENDAR,  # Keep default source
    ) -> bool:
        """Send a system trigger event to the assistant input queue."""
        try:
            if payload is None:
                payload = {}  # Use empty dict if payload is not provided

            # Create QueueTrigger instance
            queue_trigger = QueueTrigger(
                trigger_type=trigger_type,
                user_id=user_id,
                source=source,
                payload=payload,
                # Timestamp is handled by default_factory
            )

            # Serialize using Pydantic
            message_json = (
                queue_trigger.model_dump_json()
            )  # Directly serialize the QueueTrigger instance

            logger.info(
                "Sending QueueTrigger to Redis",
                user_id=user_id,
                trigger_type=trigger_type.value,
                source=source.value,
                payload_preview=str(payload)[:100],
                queue=self.settings.REDIS_QUEUE_TO_SECRETARY,
            )

            # Push the JSON string (as bytes) to Redis
            await self.redis.xadd(
                name=self.settings.REDIS_QUEUE_TO_SECRETARY,
                fields={"payload": message_json.encode("utf-8")},
            )

            logger.info("QueueTrigger sent successfully")
            return True
        except Exception as e:
            logger.error(
                "Failed to send QueueTrigger to assistant",
                error=str(e),
                user_id=user_id,
                trigger_type=trigger_type.value if trigger_type else "unknown",
                exc_info=True,
            )
            return False

    async def close(self) -> None:
        """Close Redis connection"""
        # No need for Awaitable[int] type hint, close() returns None
        await self.redis.close()
        logger.info("Redis connection closed.")
