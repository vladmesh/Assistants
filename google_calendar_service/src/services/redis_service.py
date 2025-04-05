import json
from typing import Awaitable

import redis.asyncio as redis
import structlog
from config.settings import Settings

from shared_models import HumanQueueMessage, QueueMessageSource

logger = structlog.get_logger()


class RedisService:
    """Service for working with Redis"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.redis: redis.Redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
        )

    async def send_to_assistant(self, user_id: int, message: str) -> bool:
        """Send message to assistant input queue"""
        try:
            # Create a HumanQueueMessage using shared_models
            queue_message = HumanQueueMessage(
                user_id=user_id,
                source=QueueMessageSource.CALENDAR,
                content={"message": message},
            )

            logger.info(
                "Sending message to Redis",
                user_id=user_id,
                message=message,
                queue=self.settings.REDIS_QUEUE_TO_SECRETARY,
            )

            result: Awaitable[int] = self.redis.lpush(  # type: ignore[assignment]
                self.settings.REDIS_QUEUE_TO_SECRETARY, queue_message.to_dict()
            )
            await result
            logger.info("Message sent successfully")
            return True
        except Exception as e:
            logger.error("Failed to send message to assistant", error=str(e))
            return False

    async def close(self) -> None:
        """Close Redis connection"""
        result: Awaitable[int] = self.redis.close()
        await result
