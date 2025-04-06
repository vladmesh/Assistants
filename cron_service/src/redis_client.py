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
logger.info(f"--- CREATING redis_client instance with ID: {id(redis_client)} ---")


def send_reminder_trigger(reminder_data: dict) -> None:
    """
    Sends a reminder trigger event to the assistant via Redis.

    Args:
        reminder_data: Dictionary containing the reminder details fetched from the API.
                       Expected keys: 'id', 'user_id', 'assistant_id', 'type',
                       'payload', 'trigger_at', 'created_at'.
    """
    logger.info("--- ENTERING send_reminder_trigger ---")
    try:
        # ADDED LOG:
        payload_from_data = reminder_data.get("payload", "{}")
        logger.info(f'Type of reminder_data["payload"]: {type(payload_from_data)}')
        logger.info(f'Value of reminder_data["payload"]: {payload_from_data}')

        # Construct the message payload according to the plan
        inner_payload = {}
        try:
            if isinstance(payload_from_data, str):
                inner_payload = json.loads(payload_from_data)
            elif isinstance(payload_from_data, dict):
                inner_payload = payload_from_data  # Already a dict
        except json.JSONDecodeError as decode_error:
            logger.error(f"Failed to decode inner payload: {decode_error}")
            # Handle error appropriately, maybe set default empty dict
            inner_payload = {}

        message = {
            "assistant_id": reminder_data["assistant_id"],
            "event": "reminder_triggered",
            "payload": {
                "reminder_id": reminder_data["id"],
                "user_id": reminder_data["user_id"],
                "reminder_type": reminder_data["type"],
                # Use the decoded inner_payload dictionary
                "payload": inner_payload,
                "triggered_at": datetime.now(
                    timezone.utc
                ).isoformat(),  # Use current time for trigger
                "created_at": reminder_data["created_at"],
            },
        }
        # Serialize the message to JSON string before pushing
        logger.info(f"Message object before json.dumps: {message}")
        message_json = json.dumps(message, default=str)

        # Add logging before rpush
        logger.info(
            f"Attempting to push to Redis. Queue: {OUTPUT_QUEUE}, Message: {message_json}"
        )
        logger.info(
            f"--> ID of redis_client in send_reminder_trigger: {id(redis_client)}"
        )

        redis_client.rpush(OUTPUT_QUEUE, message_json)
        # ADDED MOCK CHECK LOGS
        logger.info(
            f"--> MOCK CHECK: type of redis_client.rpush: {type(redis_client.rpush)}"
        )
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
        raise  # Restore raise
