import json
import logging
import os
from datetime import datetime, timezone

import redis

# from models import CronMessage # Remove old model import

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
# OUTPUT_QUEUE = os.getenv("REDIS_QUEUE_TO_SECRETARY", "queue:to_secretary") # Old queue
OUTPUT_QUEUE = os.getenv(
    "REDIS_QUEUE_TO_ASSISTANT", "queue:to_assistant"
)  # New queue name

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=False,  # decode_responses=False for json
)


def send_reminder_trigger(reminder_data: dict) -> None:
    """
    Sends a reminder trigger event to the assistant via Redis.

    Args:
        reminder_data: Dictionary containing the reminder details fetched from the API.
                       Expected keys: 'id', 'user_id', 'assistant_id', 'type',
                       'payload', 'trigger_at', 'created_at'.
    """
    try:
        # Construct the message payload according to the plan
        message = {
            "assistant_id": reminder_data["assistant_id"],
            "event": "reminder_triggered",
            "payload": {
                "reminder_id": reminder_data["id"],
                "user_id": reminder_data["user_id"],
                "reminder_type": reminder_data["type"],
                # Assuming payload from DB is a valid JSON string
                "payload": json.loads(reminder_data.get("payload", "{}")),
                "triggered_at": datetime.now(
                    timezone.utc
                ).isoformat(),  # Use current time for trigger
                "created_at": reminder_data["created_at"],
            },
        }
        # Serialize the message to JSON string before pushing
        message_json = json.dumps(message)

        redis_client.rpush(OUTPUT_QUEUE, message_json)
        logger.info(
            f"Reminder trigger event for {reminder_data['id']} sent to {OUTPUT_QUEUE}."
        )
    except json.JSONDecodeError as e:
        logger.error(
            f"Error decoding reminder payload for {reminder_data['id']}: {e}. Payload: {reminder_data.get('payload')}"
        )
        # Decide if we should raise or just log
    except KeyError as e:
        logger.error(
            f"Missing key in reminder_data for {reminder_data.get('id', 'unknown')}: {e}"
        )
        # Decide if we should raise or just log
    except Exception as e:
        logger.error(f"Error sending reminder trigger to Redis: {e}")
        raise  # Re-raise other exceptions
