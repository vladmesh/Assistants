import logging
import os
from uuid import UUID  # Import UUID

import requests

logger = logging.getLogger(__name__)

REST_SERVICE_URL = os.getenv("REST_SERVICE_URL", "http://rest_service:8000")
REMINDERS_ENDPOINT = f"{REST_SERVICE_URL}/api/reminders/scheduled"
REMINDER_DETAIL_ENDPOINT_TPL = (
    f"{REST_SERVICE_URL}/api/reminders/{{reminder_id}}"  # Template for detail endpoint
)


def fetch_active_reminders():
    """Fetches the list of active reminders from the REST service."""
    try:
        response = requests.get(REMINDERS_ENDPOINT, timeout=10)  # Add timeout
        response.raise_for_status()
        reminders = response.json()
        logger.info(f"Fetched {len(reminders)} active reminders.")
        return reminders
    except requests.RequestException as e:
        logger.error(f"Error fetching reminders from {REMINDERS_ENDPOINT}: {e}")
        return []
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching reminders: {e}")
        return []


def mark_reminder_completed(reminder_id: UUID) -> bool:
    """Marks a reminder as completed by sending a PATCH request to the REST service."""
    url = REMINDER_DETAIL_ENDPOINT_TPL.format(reminder_id=reminder_id)
    payload = {"status": "completed"}
    try:
        response = requests.patch(url, json=payload, timeout=10)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        logger.info(f"Successfully marked reminder {reminder_id} as completed.")
        return True
    except requests.RequestException as e:
        logger.error(f"Error updating reminder {reminder_id} status to completed: {e}")
        return False
    except Exception as e:
        logger.error(
            f"An unexpected error occurred while marking reminder {reminder_id} as completed: {e}"
        )
        return False
