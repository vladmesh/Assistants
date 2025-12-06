import logging
from collections.abc import Iterable
from typing import Any

import redis.asyncio as redis
from redis.exceptions import ResponseError

logger = logging.getLogger(__name__)


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
