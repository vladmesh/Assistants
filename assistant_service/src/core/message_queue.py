"""Message queue implementation for assistant service."""

import json
from typing import Optional, Dict, Any
import redis.asyncio as redis
from config.settings import Settings
from config.logger import get_logger

logger = get_logger(__name__)


class MessageQueue:
    """Redis-based message queue for handling assistant messages."""

    def __init__(self, settings: Settings):
        """Initialize message queue.

        Args:
            settings: Application settings
        """
        # Create Redis connection pool
        self.pool = redis.ConnectionPool(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
            max_connections=10,  # Adjust based on load
        )

        # Initialize Redis client from pool
        self.redis = redis.Redis.from_pool(self.pool)

        # Queue names
        self.input_queue = settings.INPUT_QUEUE
        self.output_queue = settings.OUTPUT_QUEUE

        logger.info(
            "Message queue initialized",
            input_queue=self.input_queue,
            output_queue=self.output_queue,
        )

    async def get_message(self, timeout: int = 0) -> Optional[Dict[str, Any]]:
        """Get message from input queue.

        Args:
            timeout: How long to wait for message in seconds. 0 means wait forever.

        Returns:
            Message dictionary or None if timeout reached
        """
        try:
            # Get message from queue (FIFO order)
            message = await self.redis.blpop(self.input_queue, timeout=timeout)
            if not message:
                return None

            # Parse message
            message_data = json.loads(message[1])

            logger.debug(
                "Message received",
                queue=self.input_queue,
                message_id=message_data.get("message_id"),
            )

            return message_data

        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse message",
                error=str(e),
                message=message[1] if message else None,
                exc_info=True,
            )
            raise

        except Exception as e:
            logger.error("Failed to get message", error=str(e), exc_info=True)
            raise

    async def send_response(self, response: Dict[str, Any]) -> None:
        """Send response to output queue.

        Args:
            response: Response dictionary to send
        """
        try:
            # Convert response to JSON
            response_json = json.dumps(response)

            # Send to queue
            await self.redis.rpush(self.output_queue, response_json)

            logger.debug(
                "Response sent",
                queue=self.output_queue,
                message_id=response.get("message_id"),
            )

        except Exception as e:
            logger.error(
                "Failed to send response",
                error=str(e),
                response=response,
                exc_info=True,
            )
            raise

    async def close(self) -> None:
        """Close Redis connections."""
        try:
            await self.redis.aclose()
            await self.pool.disconnect()

            logger.info("Message queue connections closed")

        except Exception as e:
            logger.error("Failed to close connections", error=str(e), exc_info=True)
            raise
