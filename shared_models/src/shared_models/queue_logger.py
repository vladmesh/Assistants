"""Queue message logger for REST API integration."""

import json
from enum import Enum

import httpx

from .logging import get_logger

logger = get_logger(__name__)


class QueueDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class QueueLogger:
    """Logs queue messages to REST API for observability."""

    def __init__(self, rest_service_url: str, enabled: bool = True):
        self.rest_service_url = rest_service_url.rstrip("/")
        self.enabled = enabled

    async def log_message(
        self,
        queue_name: str,
        direction: QueueDirection,
        message_type: str,
        payload: dict | str,
        correlation_id: str | None = None,
        user_id: int | None = None,
        source: str | None = None,
    ) -> None:
        """Log a queue message to REST API.

        Args:
            queue_name: Name of the queue (e.g., "to_secretary", "to_telegram")
            direction: Message direction (inbound/outbound)
            message_type: Type of message (human, tool, trigger, response)
            payload: Message payload (dict or JSON string)
            correlation_id: Request correlation ID
            user_id: User ID if applicable
            source: Message source (telegram, cron, calendar)
        """
        if not self.enabled:
            return

        try:
            payload_str = (
                json.dumps(payload, default=str)
                if isinstance(payload, dict)
                else str(payload)
            )

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    f"{self.rest_service_url}/api/queue-stats/log",
                    json={
                        "queue_name": queue_name,
                        "direction": direction.value,
                        "message_type": message_type,
                        "payload": payload_str,
                        "correlation_id": correlation_id,
                        "user_id": user_id,
                        "source": source,
                    },
                )
                response.raise_for_status()
        except Exception as e:
            logger.warning(
                "Failed to log queue message",
                error=str(e),
                queue_name=queue_name,
                direction=direction.value,
            )
