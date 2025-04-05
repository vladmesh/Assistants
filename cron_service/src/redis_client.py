import logging
import os

import redis
from models import CronMessage

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
OUTPUT_QUEUE = os.getenv("REDIS_QUEUE_TO_SECRETARY", "queue:to_secretary")

redis_client = redis.Redis(
    host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True
)


def send_notification(user_id: int, message: str, metadata: dict = None) -> None:
    """
    Отправляет уведомление через Redis в стандартизированном формате.

    Args:
        user_id: ID пользователя в базе данных
        message: Текст сообщения
        metadata: Дополнительные данные о напоминании
    """
    try:
        queue_message = CronMessage(
            user_id=user_id,
            content={"message": message, "metadata": metadata or {}},
        )

        redis_client.rpush(OUTPUT_QUEUE, queue_message.model_dump_json())
        logger.info("Уведомление успешно отправлено в Redis")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления в Redis: {str(e)}")
        raise
