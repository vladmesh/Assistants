import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

import redis

# Импортируем необходимые модели из shared_models
from shared_models import QueueMessageSource, QueueTrigger, TriggerType

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
    Sends a reminder trigger event to the assistant via Redis using QueueTrigger format.

    Args:
        reminder_data: Dictionary containing the reminder details fetched from the API.
                       Expected keys: 'id', 'user_id', 'assistant_id', 'type',
                       'payload', 'trigger_at', 'created_at'.
    """
    logger.info("--- ENTERING send_reminder_trigger (using QueueTrigger) ---")
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
            inner_payload = {}  # Use empty dict on error

        user_id = reminder_data.get("user_id")
        if user_id is None:
            logger.error(
                "Missing 'user_id' in reminder_data", extra={"data": reminder_data}
            )
            raise KeyError("'user_id' is missing in reminder_data")

        assistant_id = reminder_data.get("assistant_id")
        if assistant_id is None:
            logger.warning(
                "Missing 'assistant_id' in reminder_data, proceeding without it.",
                extra={"data": reminder_data},
            )

        # --- Create QueueTrigger Payload ---
        trigger_payload = {
            "reminder_id": reminder_data.get("id"),
            "assistant_id": str(assistant_id)
            if assistant_id
            else None,  # Ensure string or None
            "reminder_type": reminder_data.get("type"),
            "payload": inner_payload,  # Parsed payload
            "created_at": reminder_data.get("created_at"),
            # Consider adding original trigger_at if needed for logic
            # "original_trigger_at": reminder_data.get("trigger_at"),
            "triggered_at_event": datetime.now(
                timezone.utc
            ).isoformat(),  # Timestamp of this trigger event
        }

        # --- Create QueueTrigger Instance ---
        queue_trigger = QueueTrigger(
            trigger_type=TriggerType.REMINDER,
            user_id=int(user_id),  # Ensure user_id is int
            source=QueueMessageSource.CRON,
            payload=trigger_payload,
            # Timestamp is handled by default_factory in QueueTrigger
        )

        # --- Serialize using Pydantic ---
        message_json = (
            queue_trigger.model_dump_json()
        )  # Directly serialize the QueueTrigger instance

        logger.info(
            f"Attempting to push QueueTrigger to Redis. Queue: {OUTPUT_QUEUE}, Message: {message_json}"
        )
        logger.info(
            f"--> ID of redis_client in send_reminder_trigger: {id(redis_client)}"
        )

        redis_client.rpush(OUTPUT_QUEUE, message_json)

        logger.info(
            f"Reminder trigger event (as QueueTrigger) for {reminder_data.get('id')} sent to {OUTPUT_QUEUE}."
        )

    except KeyError as e:
        logger.error(
            f"Missing essential key in reminder_data for {reminder_data.get('id', 'unknown')}: {e}"
        )
    except TypeError as e:
        logger.error(
            f"Type error constructing QueueTrigger for {reminder_data.get('id', 'unknown')}: {e}"
        )
    except Exception as e:
        logger.error(
            f"Error sending reminder trigger QueueTrigger to Redis: {e}", exc_info=True
        )
        raise
