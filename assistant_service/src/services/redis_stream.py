import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as redis
from redis.exceptions import ResponseError

logger = logging.getLogger(__name__)

# DLQ Constants
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]  # seconds (exponential backoff)
DLQ_SUFFIX = ":dlq"


class RedisStreamClient:
    """Lightweight helper around Redis Streams with consumer groups."""

    def __init__(self, client: redis.Redis, stream: str, group: str, consumer: str):
        self.client = client
        self.stream = stream
        self.group = group
        self.consumer = consumer

    async def ensure_group(self) -> None:
        """Create consumer group if it does not exist."""
        try:
            await self.client.xgroup_create(
                name=self.stream, groupname=self.group, id="0", mkstream=True
            )
            logger.info(
                "Created consumer group",
                extra={"stream": self.stream, "group": self.group},
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def read(
        self,
        count: int = 1,
        block_ms: int = 5_000,
        idle_reclaim_ms: int = 60_000,
    ) -> tuple[str, dict[str, Any]] | None:
        """
        Read next message from stream, reclaiming stale pending entries if needed.
        Returns (message_id, fields) or None if nothing is available.
        """
        # Try new messages
        entries = await self.client.xreadgroup(
            groupname=self.group,
            consumername=self.consumer,
            streams={self.stream: ">"},
            count=count,
            block=block_ms,
        )
        message = self._first_entry(entries)
        if message:
            return message

        # Reclaim stale pending messages
        pending = await self.client.xautoclaim(
            name=self.stream,
            groupname=self.group,
            consumername=self.consumer,
            min_idle_time=idle_reclaim_ms,
            start_id="0-0",
            count=count,
        )
        _start_id, claimed, _ = pending
        return self._first_entry([("unused", claimed)]) if claimed else None

    async def ack(self, message_id: str) -> None:
        await self.client.xack(self.stream, self.group, message_id)

    async def add(self, payload: bytes | str) -> str:
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        return await self.client.xadd(self.stream, {"payload": payload})

    @staticmethod
    def _first_entry(
        entries: Iterable[tuple[str, list[tuple[str, dict[str, Any]]]]] | None,
    ) -> tuple[str, dict[str, Any]] | None:
        if not entries:
            return None
        stream, messages = next(iter(entries))
        if not messages:
            return None
        message_id, fields = messages[0]
        return message_id, fields

    # DLQ Methods

    @property
    def dlq_stream(self) -> str:
        """Return DLQ stream name."""
        return f"{self.stream}{DLQ_SUFFIX}"

    @staticmethod
    def get_retry_count(message_fields: dict) -> int:
        """Extract retry count from message fields."""
        retry_count = message_fields.get("retry_count") or message_fields.get(
            b"retry_count"
        )
        if retry_count is None:
            return 0
        if isinstance(retry_count, bytes):
            retry_count = retry_count.decode("utf-8")
        return int(retry_count)

    def get_retry_delay(self, retry_count: int) -> int:
        """Get delay in seconds before next retry (exponential backoff)."""
        if retry_count >= len(RETRY_DELAYS):
            return RETRY_DELAYS[-1]
        return RETRY_DELAYS[retry_count]

    async def send_to_dlq(
        self,
        original_message_id: str,
        payload: bytes | str,
        error_info: dict,
        retry_count: int,
    ) -> str:
        """Send failed message to Dead Letter Queue."""
        if isinstance(payload, str):
            payload = payload.encode("utf-8")

        dlq_entry = {
            "payload": payload,
            "original_message_id": original_message_id,
            "error_type": error_info.get("error_type", "unknown"),
            "error_message": str(error_info.get("error_message", ""))[:500],
            "retry_count": str(retry_count),
            "failed_at": datetime.now(UTC).isoformat(),
            "user_id": str(error_info.get("user_id", "")),
        }

        msg_id = await self.client.xadd(self.dlq_stream, dlq_entry)
        logger.info(
            "Message sent to DLQ",
            extra={
                "dlq_stream": self.dlq_stream,
                "original_message_id": original_message_id,
                "dlq_message_id": msg_id,
                "error_type": error_info.get("error_type"),
                "retry_count": retry_count,
            },
        )
        return msg_id

    async def read_dlq(
        self, count: int = 10, start_id: str = "0-0"
    ) -> list[tuple[str, dict]]:
        """Read messages from DLQ."""
        entries = await self.client.xrange(self.dlq_stream, min=start_id, count=count)
        return entries if entries else []

    async def delete_from_dlq(self, message_id: str) -> int:
        """Delete message from DLQ."""
        return await self.client.xdel(self.dlq_stream, message_id)

    async def get_dlq_length(self) -> int:
        """Get number of messages in DLQ."""
        try:
            return await self.client.xlen(self.dlq_stream)
        except Exception:
            return 0

    async def requeue_from_dlq(self, dlq_message_id: str) -> str | None:
        """Move message from DLQ back to main queue for retry."""
        entries = await self.client.xrange(
            self.dlq_stream, min=dlq_message_id, max=dlq_message_id, count=1
        )
        if not entries:
            return None

        _, fields = entries[0]
        payload = fields.get(b"payload") or fields.get("payload")

        # Add back to main stream
        new_id = await self.add(payload)

        # Delete from DLQ
        await self.delete_from_dlq(dlq_message_id)

        logger.info(
            "Message requeued from DLQ",
            extra={
                "dlq_message_id": dlq_message_id,
                "new_message_id": new_id,
                "stream": self.stream,
            },
        )
        return new_id
