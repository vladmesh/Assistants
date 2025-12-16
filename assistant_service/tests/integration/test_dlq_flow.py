"""E2E tests for DLQ flow: message -> error -> retry -> DLQ."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import redis.asyncio as redis

from orchestrator import AssistantOrchestrator
from services.redis_stream import MAX_RETRIES, RedisStreamClient

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def redis_client(redis_url):
    """Provide Redis client for tests."""
    client = redis.from_url(redis_url, decode_responses=False)
    try:
        await client.ping()
        yield client
    finally:
        await client.aclose()


@pytest_asyncio.fixture
async def clean_streams(redis_client):
    """Clean up test streams before and after tests."""
    test_input = "test:dlq:input"
    test_output = "test:dlq:output"
    dlq_stream = f"{test_input}:dlq"

    # Clean before test
    await redis_client.delete(test_input, test_output, dlq_stream)
    # Clean retry keys
    async for key in redis_client.scan_iter("msg_retry:*"):
        await redis_client.delete(key)

    yield {
        "input": test_input,
        "output": test_output,
        "dlq": dlq_stream,
    }

    # Clean after test
    await redis_client.delete(test_input, test_output, dlq_stream)
    async for key in redis_client.scan_iter("msg_retry:*"):
        await redis_client.delete(key)


class TestRedisStreamDLQFlow:
    """Test RedisStreamClient DLQ flow with real Redis."""

    async def test_message_sent_to_dlq_after_max_retries(
        self, redis_client, clean_streams
    ):
        """Test that message is sent to DLQ after MAX_RETRIES failures."""
        stream = RedisStreamClient(
            client=redis_client,
            stream=clean_streams["input"],
            group="test_group",
            consumer="test_consumer",
        )

        # Create consumer group
        try:
            await redis_client.xgroup_create(
                clean_streams["input"], "test_group", id="0", mkstream=True
            )
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

        # Add a message to the stream
        msg_id = await stream.add(b'{"content": "test message", "user_id": "user-1"}')
        assert msg_id is not None

        # Simulate processing failure - send to DLQ
        error_info = {
            "error_type": "ProcessingError",
            "error_message": "Simulated failure for testing",
            "user_id": "user-1",
        }
        dlq_msg_id = await stream.send_to_dlq(
            original_message_id=msg_id,
            payload=b'{"content": "test message", "user_id": "user-1"}',
            error_info=error_info,
            retry_count=MAX_RETRIES,
        )

        # Verify message is in DLQ
        dlq_messages = await stream.read_dlq(count=10)
        assert len(dlq_messages) == 1

        dlq_id, fields = dlq_messages[0]
        assert dlq_id == dlq_msg_id
        # msg_id can be bytes or string depending on Redis client config
        expected_msg_id = msg_id.decode() if isinstance(msg_id, bytes) else msg_id
        assert fields.get(b"original_message_id").decode() == expected_msg_id
        assert fields.get(b"error_type").decode() == "ProcessingError"
        assert fields.get(b"retry_count").decode() == str(MAX_RETRIES)
        assert fields.get(b"user_id").decode() == "user-1"

    async def test_dlq_message_can_be_requeued(self, redis_client, clean_streams):
        """Test that message can be moved from DLQ back to main queue."""
        stream = RedisStreamClient(
            client=redis_client,
            stream=clean_streams["input"],
            group="test_group",
            consumer="test_consumer",
        )

        # Add message directly to DLQ
        dlq_msg_id = await redis_client.xadd(
            clean_streams["dlq"],
            {
                b"payload": b'{"content": "failed message"}',
                b"original_message_id": b"orig-123",
                b"error_type": b"TestError",
                b"retry_count": b"3",
            },
        )

        # Verify DLQ has the message
        dlq_len = await stream.get_dlq_length()
        assert dlq_len == 1

        # Requeue the message
        new_msg_id = await stream.requeue_from_dlq(dlq_msg_id)
        assert new_msg_id is not None

        # Verify DLQ is empty
        dlq_len = await stream.get_dlq_length()
        assert dlq_len == 0

        # Verify message is back in main queue
        main_len = await redis_client.xlen(clean_streams["input"])
        assert main_len == 1

    async def test_dlq_stats(self, redis_client, clean_streams):
        """Test DLQ statistics."""
        stream = RedisStreamClient(
            client=redis_client,
            stream=clean_streams["input"],
            group="test_group",
            consumer="test_consumer",
        )

        # Add multiple messages to DLQ with different error types
        for i in range(3):
            await stream.send_to_dlq(
                original_message_id=f"msg-{i}",
                payload=f'{{"content": "test {i}"}}'.encode(),
                error_info={
                    "error_type": "ErrorTypeA" if i < 2 else "ErrorTypeB",
                    "error_message": f"Error {i}",
                },
                retry_count=3,
            )

        # Check DLQ length
        dlq_len = await stream.get_dlq_length()
        assert dlq_len == 3

        # Read all DLQ messages
        dlq_messages = await stream.read_dlq(count=10)
        assert len(dlq_messages) == 3

        # Verify error types
        error_types = [
            fields.get(b"error_type", b"").decode() for _, fields in dlq_messages
        ]
        assert error_types.count("ErrorTypeA") == 2
        assert error_types.count("ErrorTypeB") == 1


class TestOrchestratorRetryWithRedis:
    """Test Orchestrator retry logic with real Redis."""

    @pytest_asyncio.fixture
    async def mock_orchestrator(self, redis_client, clean_streams):
        """Create orchestrator with mocked dependencies but real Redis."""
        mock_settings = MagicMock()
        mock_settings.INPUT_QUEUE = clean_streams["input"]
        mock_settings.OUTPUT_QUEUE = clean_streams["output"]
        mock_settings.CONSUMER_GROUP = "test_group"
        mock_settings.CONSUMER_NAME = "test_consumer"

        # Create consumer group
        try:
            await redis_client.xgroup_create(
                clean_streams["input"], "test_group", id="0", mkstream=True
            )
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

        with patch.object(AssistantOrchestrator, "__init__", lambda x, y: None):
            orchestrator = AssistantOrchestrator(None)
            orchestrator.redis = redis_client
            orchestrator.settings = mock_settings
            orchestrator.input_stream = RedisStreamClient(
                client=redis_client,
                stream=clean_streams["input"],
                group="test_group",
                consumer="test_consumer",
            )
            orchestrator.output_stream = AsyncMock()
            yield orchestrator

    async def test_retry_count_increments_in_redis(
        self, mock_orchestrator, redis_client
    ):
        """Test that retry count is correctly stored and incremented in Redis."""
        message_id = "test-msg-retry-123"

        # Initial count should be 0
        count = await mock_orchestrator._get_message_retry_count(message_id)
        assert count == 0

        # Increment and verify
        new_count = await mock_orchestrator._increment_message_retry_count(message_id)
        assert new_count == 1

        # Verify stored value
        count = await mock_orchestrator._get_message_retry_count(message_id)
        assert count == 1

        # Increment again
        new_count = await mock_orchestrator._increment_message_retry_count(message_id)
        assert new_count == 2

        # Clear and verify
        await mock_orchestrator._clear_message_retry_count(message_id)
        count = await mock_orchestrator._get_message_retry_count(message_id)
        assert count == 0

    async def test_message_goes_to_dlq_after_max_retries(
        self, mock_orchestrator, redis_client, clean_streams
    ):
        """Test full flow: message fails MAX_RETRIES times and goes to DLQ."""
        payload = b'{"content": "will fail", "user_id": "user-99"}'

        # Create a real message in the stream to get a valid message ID
        message_id = await mock_orchestrator.input_stream.add(payload)
        message_id_str = (
            message_id.decode() if isinstance(message_id, bytes) else message_id
        )

        # Simulate MAX_RETRIES-1 failures (message stays in pending)
        for i in range(MAX_RETRIES - 1):
            await mock_orchestrator._handle_processing_failure(
                message_id=message_id_str,
                raw_payload=payload,
                error=ValueError(f"Failure attempt {i + 1}"),
                event=None,
            )

            # Verify message is NOT in DLQ yet
            dlq_len = await mock_orchestrator.input_stream.get_dlq_length()
            assert dlq_len == 0, f"Message went to DLQ too early at attempt {i + 1}"

            # Verify retry count
            count = await mock_orchestrator._get_message_retry_count(message_id_str)
            assert count == i + 1

        # Final failure - should go to DLQ
        await mock_orchestrator._handle_processing_failure(
            message_id=message_id_str,
            raw_payload=payload,
            error=ValueError(f"Final failure attempt {MAX_RETRIES}"),
            event=None,
        )

        # Verify message IS in DLQ
        dlq_len = await mock_orchestrator.input_stream.get_dlq_length()
        assert dlq_len == 1, "Message should be in DLQ after MAX_RETRIES"

        # Verify DLQ message contents
        dlq_messages = await mock_orchestrator.input_stream.read_dlq()
        assert len(dlq_messages) == 1

        _, fields = dlq_messages[0]
        assert fields.get(b"error_type").decode() == "ValueError"
        assert fields.get(b"retry_count").decode() == str(MAX_RETRIES)

        # Verify retry count was cleared
        count = await mock_orchestrator._get_message_retry_count(message_id_str)
        assert count == 0, "Retry count should be cleared after DLQ"
