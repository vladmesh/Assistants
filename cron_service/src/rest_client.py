"""
Async REST client for cron_service using BaseServiceClient.

Provides unified HTTP communication with retry, circuit breaker, and metrics.
"""

import asyncio
import os
from datetime import datetime
from typing import Any
from uuid import UUID

from shared_models import BaseServiceClient, ClientConfig, get_logger

logger = get_logger(__name__)

REST_SERVICE_URL = os.getenv("REST_SERVICE_URL", "http://rest_service:8000")


class CronRestClient(BaseServiceClient):
    """Async REST client for cron_service."""

    def __init__(self, base_url: str | None = None):
        config = ClientConfig(
            timeout=30.0,
            connect_timeout=5.0,
            max_retries=3,
            retry_min_wait=1.0,
            retry_max_wait=10.0,
            circuit_breaker_fail_max=5,
            circuit_breaker_reset_timeout=60.0,
        )
        super().__init__(
            base_url=base_url or REST_SERVICE_URL,
            service_name="cron_service",
            target_service="rest_service",
            config=config,
        )

    # === Reminders ===

    async def fetch_active_reminders(self) -> list[dict]:
        """Fetch active reminders for scheduling."""
        try:
            result = await self.request("GET", "/api/reminders/scheduled")
            reminders = result if isinstance(result, list) else []
            logger.info("Fetched active reminders", count=len(reminders))
            return reminders
        except Exception as e:
            logger.error("Failed to fetch reminders", error=str(e))
            return []

    async def mark_reminder_completed(self, reminder_id: UUID | str) -> bool:
        """Mark reminder as completed."""
        try:
            await self.request(
                "PATCH",
                f"/api/reminders/{reminder_id}",
                json={"status": "completed"},
            )
            logger.info("Marked reminder as completed", reminder_id=str(reminder_id))
            return True
        except Exception as e:
            logger.error(
                "Failed to mark reminder completed",
                reminder_id=str(reminder_id),
                error=str(e),
            )
            return False

    # === Global Settings ===

    async def fetch_global_settings(self) -> dict[str, Any] | None:
        """Fetch global settings."""
        try:
            result = await self.request("GET", "/api/global-settings/")
            logger.info("Fetched global settings")
            return result if isinstance(result, dict) else None
        except Exception as e:
            logger.error("Failed to fetch global settings", error=str(e))
            return None

    # === Conversations ===

    async def fetch_conversations(
        self,
        since: datetime | None = None,
        user_id: int | None = None,
        min_messages: int = 2,
        limit: int = 50,
    ) -> list[dict]:
        """Fetch conversations for memory extraction."""
        try:
            params: dict[str, Any] = {"min_messages": min_messages, "limit": limit}
            if since:
                params["since"] = since.isoformat()
            if user_id:
                params["user_id"] = user_id

            result = await self.request("GET", "/api/conversations/", params=params)
            if isinstance(result, dict):
                conversations = result.get("conversations", [])
                total_messages = result.get("total_messages", 0)
                logger.info(
                    "Fetched conversations",
                    count=len(conversations),
                    total_messages=total_messages,
                )
                return conversations
            return []
        except Exception as e:
            logger.error("Failed to fetch conversations", error=str(e))
            return []

    # === Batch Jobs ===

    async def create_batch_job(
        self,
        batch_id: str,
        user_id: int,
        assistant_id: UUID | str | None = None,
        provider: str = "openai",
        model: str = "gpt-4o-mini",
        messages_processed: int = 0,
    ) -> dict | None:
        """Create batch job record."""
        try:
            payload: dict[str, Any] = {
                "batch_id": batch_id,
                "user_id": user_id,
                "provider": provider,
                "model": model,
                "messages_processed": messages_processed,
            }
            if assistant_id:
                payload["assistant_id"] = str(assistant_id)

            result = await self.request("POST", "/api/batch-jobs/", json=payload)
            if result:
                job_id = result.get("id")
                logger.info("Created batch job", job_id=job_id, user_id=user_id)
            return result if isinstance(result, dict) else None
        except Exception as e:
            logger.error("Failed to create batch job", error=str(e))
            return None

    async def fetch_pending_batch_jobs(
        self, job_type: str = "memory_extraction"
    ) -> list[dict]:
        """Fetch pending batch jobs."""
        try:
            result = await self.request(
                "GET",
                "/api/batch-jobs/pending",
                params={"job_type": job_type},
            )
            jobs = result if isinstance(result, list) else []
            logger.info("Fetched pending batch jobs", count=len(jobs))
            return jobs
        except Exception as e:
            logger.error("Failed to fetch pending batch jobs", error=str(e))
            return []

    async def update_batch_job_status(
        self,
        job_id: UUID | str,
        status: str,
        facts_extracted: int | None = None,
        error_message: str | None = None,
    ) -> dict | None:
        """Update batch job status."""
        try:
            payload: dict[str, Any] = {"status": status}
            if facts_extracted is not None:
                payload["facts_extracted"] = facts_extracted
            if error_message is not None:
                payload["error_message"] = error_message

            result = await self.request(
                "PATCH", f"/api/batch-jobs/{job_id}", json=payload
            )
            logger.info("Updated batch job status", job_id=str(job_id), status=status)
            return result if isinstance(result, dict) else None
        except Exception as e:
            logger.error("Failed to update batch job", job_id=str(job_id), error=str(e))
            return None

    # === Job Executions ===

    async def create_job_execution(
        self,
        job_id: str,
        job_name: str,
        job_type: str,
        scheduled_at: datetime,
        user_id: int | None = None,
        reminder_id: int | str | None = None,
    ) -> dict | None:
        """Create job execution record."""
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

            result = await self.request("POST", "/api/job-executions/", json=payload)
            if result:
                logger.debug("Created job execution", execution_id=result.get("id"))
            return result if isinstance(result, dict) else None
        except Exception as e:
            logger.error("Failed to create job execution", error=str(e))
            return None

    async def start_job_execution(self, execution_id: str) -> dict | None:
        """Mark job execution as started."""
        try:
            result = await self.request(
                "PATCH", f"/api/job-executions/{execution_id}/start"
            )
            return result if isinstance(result, dict) else None
        except Exception as e:
            logger.error(
                "Failed to start job execution",
                execution_id=execution_id,
                error=str(e),
            )
            return None

    async def complete_job_execution(
        self, execution_id: str, result: str | None = None
    ) -> dict | None:
        """Mark job execution as completed."""
        try:
            payload = {"result": result} if result else None
            response = await self.request(
                "PATCH",
                f"/api/job-executions/{execution_id}/complete",
                json=payload,
            )
            return response if isinstance(response, dict) else None
        except Exception as e:
            logger.error(
                "Failed to complete job execution",
                execution_id=execution_id,
                error=str(e),
            )
            return None

    async def fail_job_execution(
        self,
        execution_id: str,
        error: str,
        error_traceback: str | None = None,
    ) -> dict | None:
        """Mark job execution as failed."""
        try:
            payload: dict[str, Any] = {"error": error}
            if error_traceback:
                payload["error_traceback"] = error_traceback

            result = await self.request(
                "PATCH",
                f"/api/job-executions/{execution_id}/fail",
                json=payload,
            )
            return result if isinstance(result, dict) else None
        except Exception as e:
            logger.error(
                "Failed to fail job execution",
                execution_id=execution_id,
                error=str(e),
            )
            return None


# Singleton instance
_client: CronRestClient | None = None


def get_rest_client() -> CronRestClient:
    """Get or create REST client singleton."""
    global _client
    if _client is None:
        _client = CronRestClient()
    return _client


async def close_rest_client() -> None:
    """Close the REST client."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None


# === Synchronous wrappers for APScheduler compatibility ===
# APScheduler's BackgroundScheduler runs jobs in threads, not async.
# These wrappers allow calling async methods from sync scheduler jobs.


def _run_async(coro):
    """Run async coroutine from sync context.

    Creates a fresh client for each call since we're creating/closing
    event loops, and httpx.AsyncClient is bound to a specific loop.
    """
    global _client
    # Clear singleton to avoid "Event loop is closed" errors
    # Each sync call needs a fresh client bound to the new loop
    _client = None

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        # Close the client before closing the loop
        if _client is not None:
            loop.run_until_complete(_client.close())
            _client = None
        loop.close()


def fetch_active_reminders() -> list[dict]:
    """Sync wrapper: Fetch active reminders."""
    client = get_rest_client()
    return _run_async(client.fetch_active_reminders())


def mark_reminder_completed(reminder_id: UUID | str) -> bool:
    """Sync wrapper: Mark reminder as completed."""
    client = get_rest_client()
    return _run_async(client.mark_reminder_completed(reminder_id))


def fetch_global_settings() -> dict[str, Any] | None:
    """Sync wrapper: Fetch global settings."""
    client = get_rest_client()
    return _run_async(client.fetch_global_settings())


def fetch_conversations(
    since: datetime | None = None,
    user_id: int | None = None,
    min_messages: int = 2,
    limit: int = 50,
) -> list[dict]:
    """Sync wrapper: Fetch conversations."""
    client = get_rest_client()
    return _run_async(
        client.fetch_conversations(
            since=since, user_id=user_id, min_messages=min_messages, limit=limit
        )
    )


def create_batch_job(
    batch_id: str,
    user_id: int,
    assistant_id: UUID | str | None = None,
    provider: str = "openai",
    model: str = "gpt-4o-mini",
    messages_processed: int = 0,
) -> dict | None:
    """Sync wrapper: Create batch job."""
    client = get_rest_client()
    return _run_async(
        client.create_batch_job(
            batch_id=batch_id,
            user_id=user_id,
            assistant_id=assistant_id,
            provider=provider,
            model=model,
            messages_processed=messages_processed,
        )
    )


def fetch_pending_batch_jobs(job_type: str = "memory_extraction") -> list[dict]:
    """Sync wrapper: Fetch pending batch jobs."""
    client = get_rest_client()
    return _run_async(client.fetch_pending_batch_jobs(job_type))


def update_batch_job_status(
    job_id: UUID | str,
    status: str,
    facts_extracted: int | None = None,
    error_message: str | None = None,
) -> dict | None:
    """Sync wrapper: Update batch job status."""
    client = get_rest_client()
    return _run_async(
        client.update_batch_job_status(
            job_id=job_id,
            status=status,
            facts_extracted=facts_extracted,
            error_message=error_message,
        )
    )


def create_job_execution(
    job_id: str,
    job_name: str,
    job_type: str,
    scheduled_at: datetime,
    user_id: int | None = None,
    reminder_id: int | str | None = None,
) -> dict | None:
    """Sync wrapper: Create job execution."""
    client = get_rest_client()
    return _run_async(
        client.create_job_execution(
            job_id=job_id,
            job_name=job_name,
            job_type=job_type,
            scheduled_at=scheduled_at,
            user_id=user_id,
            reminder_id=reminder_id,
        )
    )


def start_job_execution(execution_id: str) -> dict | None:
    """Sync wrapper: Start job execution."""
    client = get_rest_client()
    return _run_async(client.start_job_execution(execution_id))


def complete_job_execution(execution_id: str, result: str | None = None) -> dict | None:
    """Sync wrapper: Complete job execution."""
    client = get_rest_client()
    return _run_async(client.complete_job_execution(execution_id, result))


def fail_job_execution(
    execution_id: str, error: str, error_traceback: str | None = None
) -> dict | None:
    """Sync wrapper: Fail job execution."""
    client = get_rest_client()
    return _run_async(client.fail_job_execution(execution_id, error, error_traceback))
