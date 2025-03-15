import os
import json
import redis
import logging

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
OUTPUT_QUEUE = os.getenv("REDIS_QUEUE_TO_TELEGRAM", "queue:to_telegram")

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True
)

def send_notification(chat_id: int, message: str, priority: str = "normal") -> None:
    """
    Отправляет уведомление через Redis.
    
    Args:
        chat_id: ID чата в Telegram
        message: Текст сообщения
        priority: Приоритет уведомления (normal, high, low)
    """
    try:
        data = {
            "chat_id": chat_id,
            "response": message,
            "status": "success"
        }
        
        redis_client.rpush(OUTPUT_QUEUE, json.dumps(data))
        logger.info("Уведомление успешно отправлено в Redis")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления в Redis: {str(e)}") 