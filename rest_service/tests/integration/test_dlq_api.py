"""Integration tests for DLQ API endpoints."""

import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
import redis.asyncio as redis
from httpx import AsyncClient

from main import app

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
TEST_QUEUE = "test_queue"
DLQ_STREAM = f"{TEST_QUEUE}:dlq"


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator[redis.Redis, None]:
    """Provide Redis client for tests."""
    client = redis.from_url(REDIS_URL, decode_responses=True)
    try:
        await client.ping()
        await client.delete(DLQ_STREAM)
        await client.delete(TEST_QUEUE)
        yield client
        await client.delete(DLQ_STREAM)
        await client.delete(TEST_QUEUE)
    finally:
        await client.close()


@pytest_asyncio.fixture
async def dlq_client(redis_client: redis.Redis) -> AsyncGenerator[AsyncClient, None]:
    """Provide AsyncClient with Redis in app state."""
    app.state.redis_client = redis_client

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    if hasattr(app.state, "redis_client"):
        delattr(app.state, "redis_client")


@pytest_asyncio.fixture
async def dlq_message(redis_client: redis.Redis) -> str:
    """Create a test message in DLQ."""
    msg_id = await redis_client.xadd(
        DLQ_STREAM,
        {
            "payload": '{"content": "test message"}',
            "original_message_id": "orig-123-456",
            "error_type": "TestError",
            "error_message": "Test error message for testing",
            "retry_count": "3",
            "failed_at": datetime.now(UTC).isoformat(),
            "user_id": "user-42",
        },
    )
    return msg_id


class TestListDLQMessages:
    """Tests for GET /api/dlq/messages."""

    @pytest.mark.asyncio
    async def test_list_empty_dlq(self, dlq_client: AsyncClient):
        response = await dlq_client.get(f"/api/dlq/messages?queue={TEST_QUEUE}")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_messages(self, dlq_client: AsyncClient, dlq_message: str):
        response = await dlq_client.get(f"/api/dlq/messages?queue={TEST_QUEUE}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["message_id"] == dlq_message
        assert data[0]["error_type"] == "TestError"
        assert data[0]["user_id"] == "user-42"
        assert data[0]["retry_count"] == 3

    @pytest.mark.asyncio
    async def test_filter_by_error_type(
        self, dlq_client: AsyncClient, redis_client: redis.Redis, dlq_message: str
    ):
        await redis_client.xadd(
            DLQ_STREAM,
            {
                "payload": "other",
                "original_message_id": "orig-other",
                "error_type": "OtherError",
                "error_message": "Other error",
                "retry_count": "1",
                "failed_at": datetime.now(UTC).isoformat(),
            },
        )

        response = await dlq_client.get(
            f"/api/dlq/messages?queue={TEST_QUEUE}&error_type=TestError"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["error_type"] == "TestError"

    @pytest.mark.asyncio
    async def test_filter_by_user_id(self, dlq_client: AsyncClient, dlq_message: str):
        response = await dlq_client.get(
            f"/api/dlq/messages?queue={TEST_QUEUE}&user_id=user-42"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        response = await dlq_client.get(
            f"/api/dlq/messages?queue={TEST_QUEUE}&user_id=nonexistent"
        )
        assert response.status_code == 200
        assert response.json() == []


class TestDLQStats:
    """Tests for GET /api/dlq/stats."""

    @pytest.mark.asyncio
    async def test_stats_empty_dlq(self, dlq_client: AsyncClient):
        response = await dlq_client.get(f"/api/dlq/stats?queue={TEST_QUEUE}")
        assert response.status_code == 200
        data = response.json()
        assert data["queue_name"] == TEST_QUEUE
        assert data["total_messages"] == 0
        assert data["by_error_type"] == {}

    @pytest.mark.asyncio
    async def test_stats_with_messages(
        self, dlq_client: AsyncClient, redis_client: redis.Redis, dlq_message: str
    ):
        await redis_client.xadd(
            DLQ_STREAM,
            {
                "payload": "msg2",
                "original_message_id": "orig-2",
                "error_type": "TestError",
                "retry_count": "2",
                "failed_at": datetime.now(UTC).isoformat(),
            },
        )
        await redis_client.xadd(
            DLQ_STREAM,
            {
                "payload": "msg3",
                "original_message_id": "orig-3",
                "error_type": "ValidationError",
                "retry_count": "1",
                "failed_at": datetime.now(UTC).isoformat(),
            },
        )

        response = await dlq_client.get(f"/api/dlq/stats?queue={TEST_QUEUE}")
        assert response.status_code == 200
        data = response.json()
        assert data["total_messages"] == 3
        assert data["by_error_type"]["TestError"] == 2
        assert data["by_error_type"]["ValidationError"] == 1
        assert data["oldest_message_at"] is not None
        assert data["newest_message_at"] is not None


class TestRetryDLQMessage:
    """Tests for POST /api/dlq/messages/{message_id}/retry."""

    @pytest.mark.asyncio
    async def test_retry_message(
        self, dlq_client: AsyncClient, redis_client: redis.Redis, dlq_message: str
    ):
        response = await dlq_client.post(
            f"/api/dlq/messages/{dlq_message}/retry?queue={TEST_QUEUE}"
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "requeued"
        assert data["original_dlq_message_id"] == dlq_message
        assert "new_message_id" in data

        dlq_len = await redis_client.xlen(DLQ_STREAM)
        assert dlq_len == 0

        queue_len = await redis_client.xlen(TEST_QUEUE)
        assert queue_len == 1

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Starlette ExceptionGroup issue with httpx in tests")
    async def test_retry_nonexistent_message(self, dlq_client: AsyncClient):
        response = await dlq_client.post(
            f"/api/dlq/messages/nonexistent-id/retry?queue={TEST_QUEUE}"
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestDeleteDLQMessage:
    """Tests for DELETE /api/dlq/messages/{message_id}."""

    @pytest.mark.asyncio
    async def test_delete_message(
        self, dlq_client: AsyncClient, redis_client: redis.Redis, dlq_message: str
    ):
        response = await dlq_client.delete(
            f"/api/dlq/messages/{dlq_message}?queue={TEST_QUEUE}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"
        assert data["message_id"] == dlq_message

        dlq_len = await redis_client.xlen(DLQ_STREAM)
        assert dlq_len == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent_message(self, dlq_client: AsyncClient):
        response = await dlq_client.delete(
            f"/api/dlq/messages/nonexistent-id?queue={TEST_QUEUE}"
        )
        assert response.status_code == 404


class TestPurgeDLQ:
    """Tests for DELETE /api/dlq/messages (purge)."""

    @pytest.mark.asyncio
    async def test_purge_all(
        self, dlq_client: AsyncClient, redis_client: redis.Redis, dlq_message: str
    ):
        await redis_client.xadd(DLQ_STREAM, {"payload": "msg2", "error_type": "Error2"})

        response = await dlq_client.delete(f"/api/dlq/messages?queue={TEST_QUEUE}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "purged"

        dlq_len = await redis_client.xlen(DLQ_STREAM)
        assert dlq_len == 0

    @pytest.mark.asyncio
    async def test_purge_by_error_type(
        self, dlq_client: AsyncClient, redis_client: redis.Redis, dlq_message: str
    ):
        await redis_client.xadd(
            DLQ_STREAM,
            {"payload": "keep", "original_message_id": "k", "error_type": "KeepError"},
        )

        response = await dlq_client.delete(
            f"/api/dlq/messages?queue={TEST_QUEUE}&error_type=TestError"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "purged"
        assert data["deleted_count"] == 1
        assert data["filter"] == "TestError"

        dlq_len = await redis_client.xlen(DLQ_STREAM)
        assert dlq_len == 1


class TestRedisUnavailable:
    """Tests for Redis unavailability handling."""

    @pytest.mark.asyncio
    async def test_redis_not_available(self):
        if hasattr(app.state, "redis_client"):
            delattr(app.state, "redis_client")

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(f"/api/dlq/messages?queue={TEST_QUEUE}")
            assert response.status_code == 503
            assert "Redis not available" in response.json()["detail"]
