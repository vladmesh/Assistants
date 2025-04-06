import logging
import os

import requests

logger = logging.getLogger(__name__)

REST_SERVICE_URL = os.getenv("REST_SERVICE_URL", "http://rest_service:8000")
REMINDERS_ENDPOINT = f"{REST_SERVICE_URL}/reminders/scheduled"


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
