import json

import redis.asyncio as redis
import structlog

from src.config.settings import Settings

logger = structlog.get_logger()


class RedisService:
    """Service for working with Redis"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
        )

    async def send_to_assistant(self, user_id: int, message: str) -> bool:
        """Send message to assistant input queue"""
        try:
            data = {"user_id": user_id, "text": message}
            logger.info(
                "Sending message to Redis",
                user_id=user_id,
                message=message,
                queue=self.settings.REDIS_QUEUE_TO_SECRETARY,
            )
            await self.redis.lpush(
                self.settings.REDIS_QUEUE_TO_SECRETARY, json.dumps(data)
            )
            logger.info("Message sent successfully")
            return True
        except Exception as e:
            logger.error("Failed to send message to assistant", error=str(e))
            return False

    async def close(self):
        """Close Redis connection"""
        await self.redis.close()
