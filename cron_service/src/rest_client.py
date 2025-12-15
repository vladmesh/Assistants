import logging
import os
from datetime import datetime
from typing import Any
from uuid import UUID

import requests

logger = logging.getLogger(__name__)

REST_SERVICE_URL = os.getenv("REST_SERVICE_URL", "http://rest_service:8000")
REMINDERS_ENDPOINT = f"{REST_SERVICE_URL}/api/reminders/scheduled"
REMINDER_DETAIL_ENDPOINT_TPL = f"{REST_SERVICE_URL}/api/reminders/{{reminder_id}}"
GLOBAL_SETTINGS_ENDPOINT = f"{REST_SERVICE_URL}/api/global-settings/"
CONVERSATIONS_ENDPOINT = f"{REST_SERVICE_URL}/api/conversations/"
BATCH_JOBS_ENDPOINT = f"{REST_SERVICE_URL}/api/batch-jobs/"
JOB_EXECUTIONS_ENDPOINT = f"{REST_SERVICE_URL}/api/job-executions/"


def fetch_active_reminders() -> list[dict]:
    """Fetches the list of active reminders from the REST service."""
    try:
        response = requests.get(REMINDERS_ENDPOINT, timeout=10)
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
        response.raise_for_status()
        logger.info(f"Successfully marked reminder {reminder_id} as completed.")
        return True
    except requests.RequestException as e:
        logger.error(f"Error updating reminder {reminder_id} status to completed: {e}")
        return False
    except Exception as e:
        logger.error(
            "An unexpected error occurred while marking reminder %s as completed: %s",
            reminder_id,
            e,
        )
        return False


def fetch_global_settings() -> dict[str, Any] | None:
    """Fetches global settings from the REST service."""
    try:
        response = requests.get(GLOBAL_SETTINGS_ENDPOINT, timeout=10)
        response.raise_for_status()
        settings = response.json()
        logger.info("Fetched global settings.")
        return settings
    except requests.RequestException as e:
        logger.error(f"Error fetching global settings: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching global settings: {e}")
        return None


def fetch_conversations(
    since: datetime | None = None,
    user_id: int | None = None,
    min_messages: int = 2,
    limit: int = 50,
) -> list[dict]:
    """Fetches conversations grouped by user/assistant for fact extraction."""
    try:
        params: dict[str, Any] = {
            "min_messages": min_messages,
            "limit": limit,
        }
        if since:
            params["since"] = since.isoformat()
        if user_id:
            params["user_id"] = user_id

        response = requests.get(CONVERSATIONS_ENDPOINT, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        conversations = data.get("conversations", [])
        logger.info(
            f"Fetched {len(conversations)} conversations "
            f"({data.get('total_messages', 0)} messages total)."
        )
        return conversations
    except requests.RequestException as e:
        logger.error(f"Error fetching conversations: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching conversations: {e}")
        return []


def create_batch_job(
    batch_id: str,
    user_id: int,
    assistant_id: UUID | None = None,
    provider: str = "openai",
    model: str = "gpt-4o-mini",
    messages_processed: int = 0,
) -> dict | None:
    """Creates a batch job record for tracking."""
    try:
        payload = {
            "batch_id": batch_id,
            "user_id": user_id,
            "provider": provider,
            "model": model,
            "messages_processed": messages_processed,
        }
        if assistant_id:
            payload["assistant_id"] = str(assistant_id)

        response = requests.post(BATCH_JOBS_ENDPOINT, json=payload, timeout=10)
        response.raise_for_status()
        job = response.json()
        logger.info(f"Created batch job {job.get('id')} for user {user_id}.")
        return job
    except requests.RequestException as e:
        logger.error(f"Error creating batch job: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error creating batch job: {e}")
        return None


def fetch_pending_batch_jobs(job_type: str = "memory_extraction") -> list[dict]:
    """Fetches pending batch jobs for processing."""
    try:
        url = f"{BATCH_JOBS_ENDPOINT}pending"
        params = {"job_type": job_type}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        jobs = response.json()
        logger.info(f"Fetched {len(jobs)} pending batch jobs.")
        return jobs
    except requests.RequestException as e:
        logger.error(f"Error fetching pending batch jobs: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching pending batch jobs: {e}")
        return []


def update_batch_job_status(
    job_id: UUID,
    status: str,
    facts_extracted: int | None = None,
    error_message: str | None = None,
) -> dict | None:
    """Updates a batch job status."""
    try:
        url = f"{BATCH_JOBS_ENDPOINT}{job_id}"
        payload: dict[str, Any] = {"status": status}
        if facts_extracted is not None:
            payload["facts_extracted"] = facts_extracted
        if error_message is not None:
            payload["error_message"] = error_message

        response = requests.patch(url, json=payload, timeout=10)
        response.raise_for_status()
        job = response.json()
        logger.info(f"Updated batch job {job_id} status to {status}.")
        return job
    except requests.RequestException as e:
        logger.error(f"Error updating batch job {job_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error updating batch job {job_id}: {e}")
        return None


# === Job Execution Tracking ===


def create_job_execution(
    job_id: str,
    job_name: str,
    job_type: str,
    scheduled_at: datetime,
    user_id: int | None = None,
    reminder_id: int | None = None,
) -> dict | None:
    """Creates a job execution record for tracking."""
    try:
        payload: dict[str, Any] = {
            "job_id": job_id,
            "job_name": job_name,
            "job_type": job_type,
            "scheduled_at": scheduled_at.isoformat(),
        }
        if user_id is not None:
            payload["user_id"] = user_id
        if reminder_id is not None:
            payload["reminder_id"] = reminder_id

        response = requests.post(JOB_EXECUTIONS_ENDPOINT, json=payload, timeout=10)
        response.raise_for_status()
        execution = response.json()
        logger.debug(f"Created job execution {execution.get('id')}.")
        return execution
    except requests.RequestException as e:
        logger.error(f"Error creating job execution: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error creating job execution: {e}")
        return None


def start_job_execution(execution_id: str) -> dict | None:
    """Marks a job execution as started."""
    try:
        url = f"{JOB_EXECUTIONS_ENDPOINT}{execution_id}/start"
        response = requests.patch(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error starting job execution {execution_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error starting job execution {execution_id}: {e}")
        return None


def complete_job_execution(execution_id: str, result: str | None = None) -> dict | None:
    """Marks a job execution as completed."""
    try:
        url = f"{JOB_EXECUTIONS_ENDPOINT}{execution_id}/complete"
        payload = {"result": result} if result else None
        response = requests.patch(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error completing job execution {execution_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error completing job execution {execution_id}: {e}")
        return None


def fail_job_execution(
    execution_id: str, error: str, error_traceback: str | None = None
) -> dict | None:
    """Marks a job execution as failed."""
    try:
        url = f"{JOB_EXECUTIONS_ENDPOINT}{execution_id}/fail"
        payload: dict[str, Any] = {"error": error}
        if error_traceback:
            payload["error_traceback"] = error_traceback
        response = requests.patch(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error failing job execution {execution_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error failing job execution {execution_id}: {e}")
        return None
