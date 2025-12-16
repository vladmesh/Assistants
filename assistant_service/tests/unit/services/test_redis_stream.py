"""Unit tests for RedisStreamClient DLQ functionality."""

from unittest.mock import AsyncMock

import pytest

from services.redis_stream import (
    DLQ_SUFFIX,
    MAX_RETRIES,
    RETRY_DELAYS,
    RedisStreamClient,
)


@pytest.fixture
def mock_redis():
    return AsyncMock()


@pytest.fixture
def stream_client(mock_redis):
    return RedisStreamClient(
        client=mock_redis,
        stream="test_stream",
        group="test_group",
        consumer="test_consumer",
    )


class TestConstants:
    def test_max_retries_is_positive(self):
        assert MAX_RETRIES > 0

    def test_retry_delays_not_empty(self):
        assert len(RETRY_DELAYS) > 0

    def test_retry_delays_are_positive(self):
        assert all(d > 0 for d in RETRY_DELAYS)

    def test_dlq_suffix(self):
        assert DLQ_SUFFIX == ":dlq"


class TestDLQStreamProperty:
    def test_dlq_stream_name(self, stream_client):
        assert stream_client.dlq_stream == "test_stream:dlq"

    def test_dlq_stream_with_different_name(self, mock_redis):
        client = RedisStreamClient(
            client=mock_redis,
            stream="my_queue",
            group="g",
            consumer="c",
        )
        assert client.dlq_stream == "my_queue:dlq"


class TestGetRetryCount:
    def test_returns_zero_when_no_count(self):
        assert RedisStreamClient.get_retry_count({}) == 0

    def test_returns_zero_when_none(self):
        assert RedisStreamClient.get_retry_count({"retry_count": None}) == 0

    def test_returns_count_from_string(self):
        assert RedisStreamClient.get_retry_count({"retry_count": "3"}) == 3

    def test_returns_count_from_int_string(self):
        assert RedisStreamClient.get_retry_count({"retry_count": "0"}) == 0

    def test_returns_count_from_bytes(self):
        assert RedisStreamClient.get_retry_count({b"retry_count": b"2"}) == 2

    def test_returns_count_from_bytes_key_string_value(self):
        assert RedisStreamClient.get_retry_count({b"retry_count": "5"}) == 5

    def test_prefers_string_key_over_bytes(self):
        # String key should be found first
        result = RedisStreamClient.get_retry_count({"retry_count": "10"})
        assert result == 10


class TestGetRetryDelay:
    def test_returns_first_delay_for_zero(self, stream_client):
        assert stream_client.get_retry_delay(0) == RETRY_DELAYS[0]

    def test_returns_correct_delays(self, stream_client):
        for i, expected in enumerate(RETRY_DELAYS):
            assert stream_client.get_retry_delay(i) == expected

    def test_returns_last_delay_for_high_count(self, stream_client):
        assert stream_client.get_retry_delay(100) == RETRY_DELAYS[-1]
        assert stream_client.get_retry_delay(len(RETRY_DELAYS)) == RETRY_DELAYS[-1]


class TestSendToDLQ:
    @pytest.mark.asyncio
    async def test_sends_message_to_dlq(self, stream_client, mock_redis):
        mock_redis.xadd.return_value = "1234-0"

        result = await stream_client.send_to_dlq(
            original_message_id="orig-123",
            payload=b'{"test": "data"}',
            error_info={
                "error_type": "ValueError",
                "error_message": "Test error",
                "user_id": "user-1",
            },
            retry_count=3,
        )

        assert result == "1234-0"
        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        assert call_args[0][0] == "test_stream:dlq"

    @pytest.mark.asyncio
    async def test_sends_string_payload(self, stream_client, mock_redis):
        mock_redis.xadd.return_value = "5678-0"

        await stream_client.send_to_dlq(
            original_message_id="orig-456",
            payload="string payload",
            error_info={"error_type": "TestError"},
            retry_count=1,
        )

        call_args = mock_redis.xadd.call_args
        entry = call_args[0][1]
        assert entry["payload"] == b"string payload"

    @pytest.mark.asyncio
    async def test_truncates_long_error_message(self, stream_client, mock_redis):
        mock_redis.xadd.return_value = "9999-0"
        long_message = "x" * 1000

        await stream_client.send_to_dlq(
            original_message_id="orig-789",
            payload=b"test",
            error_info={"error_message": long_message},
            retry_count=2,
        )

        call_args = mock_redis.xadd.call_args
        entry = call_args[0][1]
        assert len(entry["error_message"]) <= 500

    @pytest.mark.asyncio
    async def test_includes_all_required_fields(self, stream_client, mock_redis):
        mock_redis.xadd.return_value = "1111-0"

        await stream_client.send_to_dlq(
            original_message_id="orig-111",
            payload=b"test",
            error_info={
                "error_type": "CustomError",
                "error_message": "Something failed",
                "user_id": "user-42",
            },
            retry_count=3,
        )

        call_args = mock_redis.xadd.call_args
        entry = call_args[0][1]

        assert entry["original_message_id"] == "orig-111"
        assert entry["error_type"] == "CustomError"
        assert entry["error_message"] == "Something failed"
        assert entry["retry_count"] == "3"
        assert entry["user_id"] == "user-42"
        assert "failed_at" in entry


class TestReadDLQ:
    @pytest.mark.asyncio
    async def test_reads_messages_from_dlq(self, stream_client, mock_redis):
        mock_redis.xrange.return_value = [
            ("msg-1", {"payload": b"data1"}),
            ("msg-2", {"payload": b"data2"}),
        ]

        result = await stream_client.read_dlq(count=10)

        assert len(result) == 2
        mock_redis.xrange.assert_called_once_with(
            "test_stream:dlq", min="0-0", count=10
        )

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_messages(self, stream_client, mock_redis):
        mock_redis.xrange.return_value = None

        result = await stream_client.read_dlq()

        assert result == []

    @pytest.mark.asyncio
    async def test_uses_custom_start_id(self, stream_client, mock_redis):
        mock_redis.xrange.return_value = []

        await stream_client.read_dlq(start_id="1234-0")

        mock_redis.xrange.assert_called_once_with(
            "test_stream:dlq", min="1234-0", count=10
        )


class TestDeleteFromDLQ:
    @pytest.mark.asyncio
    async def test_deletes_message(self, stream_client, mock_redis):
        mock_redis.xdel.return_value = 1

        result = await stream_client.delete_from_dlq("msg-123")

        assert result == 1
        mock_redis.xdel.assert_called_once_with("test_stream:dlq", "msg-123")


class TestGetDLQLength:
    @pytest.mark.asyncio
    async def test_returns_length(self, stream_client, mock_redis):
        mock_redis.xlen.return_value = 42

        result = await stream_client.get_dlq_length()

        assert result == 42
        mock_redis.xlen.assert_called_once_with("test_stream:dlq")

    @pytest.mark.asyncio
    async def test_returns_zero_on_error(self, stream_client, mock_redis):
        mock_redis.xlen.side_effect = Exception("Redis error")

        result = await stream_client.get_dlq_length()

        assert result == 0


class TestRequeueFromDLQ:
    @pytest.mark.asyncio
    async def test_requeues_message(self, stream_client, mock_redis):
        mock_redis.xrange.return_value = [
            ("dlq-msg-1", {b"payload": b'{"content": "test"}'})
        ]
        mock_redis.xadd.return_value = "new-msg-1"
        mock_redis.xdel.return_value = 1

        result = await stream_client.requeue_from_dlq("dlq-msg-1")

        assert result == "new-msg-1"
        mock_redis.xrange.assert_called_once()
        mock_redis.xadd.assert_called_once()
        mock_redis.xdel.assert_called_once_with("test_stream:dlq", "dlq-msg-1")

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, stream_client, mock_redis):
        mock_redis.xrange.return_value = []

        result = await stream_client.requeue_from_dlq("nonexistent")

        assert result is None
        mock_redis.xadd.assert_not_called()
        mock_redis.xdel.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_string_payload_key(self, stream_client, mock_redis):
        mock_redis.xrange.return_value = [("dlq-msg-2", {"payload": b"test data"})]
        mock_redis.xadd.return_value = "new-msg-2"
        mock_redis.xdel.return_value = 1

        result = await stream_client.requeue_from_dlq("dlq-msg-2")

        assert result == "new-msg-2"
