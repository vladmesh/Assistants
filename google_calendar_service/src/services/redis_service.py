import json
import redis.asyncio as redis
from src.config.settings import Settings
import structlog

logger = structlog.get_logger()

class RedisService:
    """Service for working with Redis"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
    
    async def send_to_assistant(self, user_id: int, chat_id: int, message: str) -> bool:
        """Send message to assistant input queue"""
        try:
            data = {
                "user_id": user_id,
                "chat_id": chat_id,
                "message": message
            }
            await self.redis.lpush(self.settings.ASSISTANT_INPUT_QUEUE, json.dumps(data))
            return True
        except Exception as e:
            logger.error("Failed to send message to assistant", error=str(e))
            return False
    
    async def close(self):
        """Close Redis connection"""
        await self.redis.close() 