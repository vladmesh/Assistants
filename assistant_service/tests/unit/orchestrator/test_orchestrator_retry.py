"""Unit tests for Orchestrator DLQ and retry logic."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from orchestrator import (
    MAX_RETRIES,
    RETRY_KEY_PREFIX,
    RETRY_KEY_TTL,
    AssistantOrchestrator,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_orchestrator(mock_settings, mocker, mock_rest_client):
    """Create orchestrator with mocked dependencies."""
    mocker.patch("orchestrator.RestServiceClient", return_value=mock_rest_client)
    mocker.patch("orchestrator.AssistantFactory", return_value=AsyncMock())

    orchestrator = AssistantOrchestrator(mock_settings)
    orchestrator.redis = AsyncMock()
    orchestrator.input_stream = AsyncMock()
    orchestrator.output_stream = AsyncMock()
    return orchestrator


class TestRetryCountManagement:
    async def test_get_message_retry_count_returns_zero_when_not_set(
        self, mock_orchestrator
    ):
        mock_orchestrator.redis.get.return_value = None

        result = await mock_orchestrator._get_message_retry_count("msg-123")

        assert result == 0
        mock_orchestrator.redis.get.assert_called_once_with(
            f"{RETRY_KEY_PREFIX}msg-123"
        )

    async def test_get_message_retry_count_returns_stored_value(
        self, mock_orchestrator
    ):
        mock_orchestrator.redis.get.return_value = b"3"

        result = await mock_orchestrator._get_message_retry_count("msg-456")

        assert result == 3

    async def test_increment_message_retry_count(self, mock_orchestrator):
        mock_orchestrator.redis.incr.return_value = 2

        result = await mock_orchestrator._increment_message_retry_count("msg-789")

        assert result == 2
        mock_orchestrator.redis.incr.assert_called_once_with(
            f"{RETRY_KEY_PREFIX}msg-789"
        )
        mock_orchestrator.redis.expire.assert_called_once_with(
            f"{RETRY_KEY_PREFIX}msg-789", RETRY_KEY_TTL
        )

    async def test_clear_message_retry_count(self, mock_orchestrator):
        await mock_orchestrator._clear_message_retry_count("msg-999")

        mock_orchestrator.redis.delete.assert_called_once_with(
            f"{RETRY_KEY_PREFIX}msg-999"
        )


class TestHandleProcessingFailure:
    async def test_sends_to_dlq_after_max_retries(self, mock_orchestrator):
        mock_orchestrator.redis.incr.return_value = MAX_RETRIES

        await mock_orchestrator._handle_processing_failure(
            message_id="msg-dlq-1",
            raw_payload=b'{"content": "test"}',
            error=ValueError("Test error"),
            event=None,
        )

        # Should send to DLQ
        mock_orchestrator.input_stream.send_to_dlq.assert_called_once()
        call_args = mock_orchestrator.input_stream.send_to_dlq.call_args
        assert call_args.kwargs["original_message_id"] == "msg-dlq-1"
        assert call_args.kwargs["retry_count"] == MAX_RETRIES
        assert call_args.kwargs["error_info"]["error_type"] == "ValueError"

        # Should ACK after DLQ
        mock_orchestrator.input_stream.ack.assert_called_once_with("msg-dlq-1")

        # Should clear retry count
        mock_orchestrator.redis.delete.assert_called()

    async def test_does_not_ack_before_max_retries(self, mock_orchestrator):
        mock_orchestrator.redis.incr.return_value = 1  # First retry

        await mock_orchestrator._handle_processing_failure(
            message_id="msg-retry-1",
            raw_payload=b"test",
            error=ValueError("Test error"),
            event=None,
        )

        # Should NOT send to DLQ
        mock_orchestrator.input_stream.send_to_dlq.assert_not_called()
        # Should NOT ACK
        mock_orchestrator.input_stream.ack.assert_not_called()
        # Should NOT clear retry count
        mock_orchestrator.redis.delete.assert_not_called()

    async def test_extracts_user_id_from_event(self, mock_orchestrator):
        mock_orchestrator.redis.incr.return_value = MAX_RETRIES
        mock_event = MagicMock()
        mock_event.user_id = "user-42"

        await mock_orchestrator._handle_processing_failure(
            message_id="msg-user-1",
            raw_payload=b"test",
            error=Exception("Error"),
            event=mock_event,
        )

        call_args = mock_orchestrator.input_stream.send_to_dlq.call_args
        assert call_args.kwargs["error_info"]["user_id"] == "user-42"

    async def test_handles_dlq_send_failure(self, mock_orchestrator):
        mock_orchestrator.redis.incr.return_value = MAX_RETRIES
        mock_orchestrator.input_stream.send_to_dlq.side_effect = Exception("DLQ failed")

        # Should not raise, just log error
        await mock_orchestrator._handle_processing_failure(
            message_id="msg-dlq-fail",
            raw_payload=b"test",
            error=ValueError("Original error"),
            event=None,
        )

        # ACK should not be called since DLQ failed
        mock_orchestrator.input_stream.ack.assert_not_called()


class TestListenForMessagesRetryLogic:
    """Integration tests for listen_for_messages would require more complex setup.
    The core retry logic is tested via TestHandleProcessingFailure and
    TestRetryCountManagement above.
    """

    pass


class TestConstants:
    def test_retry_key_prefix(self):
        assert RETRY_KEY_PREFIX == "msg_retry:"

    def test_retry_key_ttl(self):
        assert RETRY_KEY_TTL == 3600

    def test_max_retries_imported(self):
        assert MAX_RETRIES == 3
