import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

import redis

# Импортируем необходимые модели из shared_models
from shared_models import QueueMessageContent, QueueMessageSource, QueueMessageType

# from models import CronMessage # Remove old model import

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
# OUTPUT_QUEUE = os.getenv("REDIS_QUEUE_TO_SECRETARY", "queue:to_secretary") # Old queue
OUTPUT_QUEUE = os.getenv("REDIS_QUEUE_TO_SECRETARY")  # Use Secretary queue
if not OUTPUT_QUEUE:
    logger.critical("Environment variable REDIS_QUEUE_TO_SECRETARY is not set.")
    # Можно либо вызвать sys.exit(1), либо использовать значение по умолчанию
    OUTPUT_QUEUE = "queue:to_secretary"  # Пример значения по умолчанию

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=False,  # decode_responses=False for json
)
logger.info(f"--- CREATING redis_client instance with ID: {id(redis_client)} ---")


def send_reminder_trigger(reminder_data: Dict[str, Any]) -> None:
    """
    Sends a reminder trigger event to the assistant via Redis using QueueMessage format.

    Args:
        reminder_data: Dictionary containing the reminder details fetched from the API.
                       Expected keys: 'id', 'user_id', 'assistant_id', 'type',
                       'payload', 'trigger_at', 'created_at'.
    """
    logger.info("--- ENTERING send_reminder_trigger ---")
    try:
        payload_from_data = reminder_data.get("payload", "{}")
        logger.info(f'Type of reminder_data["payload"]: {type(payload_from_data)}')
        logger.info(f'Value of reminder_data["payload"]: {payload_from_data}')

        inner_payload = {}
        try:
            if isinstance(payload_from_data, str):
                inner_payload = json.loads(payload_from_data)
            elif isinstance(payload_from_data, dict):
                inner_payload = payload_from_data  # Already a dict
        except json.JSONDecodeError as decode_error:
            logger.error(f"Failed to decode inner payload: {decode_error}")
            inner_payload = {}  # Используем пустой словарь при ошибке

        # Извлекаем user_id, проверяем наличие
        user_id = reminder_data.get("user_id")
        if user_id is None:
            logger.error(
                "Missing 'user_id' in reminder_data", extra={"data": reminder_data}
            )
            # Можно либо вернуть, либо выбросить исключение, чтобы указать на ошибку
            # return
            raise KeyError("'user_id' is missing in reminder_data")

        # Формируем metadata для QueueMessageContent
        metadata = {
            "tool_name": "reminder_trigger",  # Указываем имя "инструмента"
            "reminder_id": reminder_data.get("id"),
            "assistant_id": reminder_data.get("assistant_id"),
            "reminder_type": reminder_data.get("type"),
            "payload": inner_payload,  # Распарсенный payload
            "created_at": reminder_data.get("created_at"),
            # Можно добавить исходное trigger_at, если нужно
            # "original_trigger_at": reminder_data.get("trigger_at"),
            "triggered_at_event": datetime.now(timezone.utc).isoformat(),
        }

        # Формируем QueueMessageContent
        message_content_dict = QueueMessageContent(
            message=f"Reminder triggered: {reminder_data.get('id', 'N/A')}",  # Описательное сообщение
            metadata=metadata,
        ).model_dump()  # Используем model_dump для Pydantic v2+

        # Формируем основной объект сообщения QueueMessage
        queue_message_dict = {
            "type": QueueMessageType.TOOL.value,
            "user_id": int(user_id),  # Убедимся, что user_id - это int
            "source": QueueMessageSource.CRON.value,
            "content": message_content_dict,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Сериализуем и отправляем
        logger.info(f"QueueMessage object before json.dumps: {queue_message_dict}")
        message_json = json.dumps(queue_message_dict, default=str)

        logger.info(
            f"Attempting to push QueueMessage to Redis. Queue: {OUTPUT_QUEUE}, Message: {message_json}"
        )
        logger.info(
            f"--> ID of redis_client in send_reminder_trigger: {id(redis_client)}"
        )

        redis_client.rpush(OUTPUT_QUEUE, message_json)

        logger.info(
            f"Reminder trigger event (as QueueMessage) for {reminder_data.get('id')} sent to {OUTPUT_QUEUE}."
        )

    except json.JSONDecodeError as e:  # Эта ошибка теперь обрабатывается выше
        logger.error(
            f"Error encoding final message to JSON for {reminder_data.get('id', 'unknown')}: {e}"
        )
    except KeyError as e:
        # KeyError теперь может возникнуть, если 'user_id' отсутствует и мы вызываем raise
        logger.error(
            f"Missing essential key in reminder_data for {reminder_data.get('id', 'unknown')}: {e}"
        )
    except TypeError as e:
        # Например, если user_id не может быть преобразован в int
        logger.error(
            f"Type error constructing QueueMessage for {reminder_data.get('id', 'unknown')}: {e}"
        )
    except Exception as e:
        logger.error(
            f"Error sending reminder trigger QueueMessage to Redis: {e}", exc_info=True
        )
        raise
