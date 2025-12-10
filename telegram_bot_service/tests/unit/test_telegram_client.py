# telegram_bot_service/tests/unit/test_telegram_client.py
"""Unit tests for Telegram client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_settings():
    """Mock settings for tests."""
    with patch("clients.telegram.settings") as mock:
        mock.telegram_token = "fake_bot_credential"
        yield mock


@pytest.fixture
def telegram_client(mock_settings):
    """Create TelegramClient instance with mocked settings."""
    from clients.telegram import TelegramClient

    return TelegramClient()


class TestTelegramClientInit:
    """Tests for TelegramClient initialization."""

    def test_client_init(self, telegram_client):
        """Test client initializes with correct base URL."""
        assert "fake_bot_credential" in telegram_client.base_url
        assert telegram_client.session is None


class TestTelegramClientContextManager:
    """Tests for TelegramClient context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_creates_session(self, telegram_client):
        """Test that entering context creates aiohttp session."""
        async with telegram_client:
            assert telegram_client.session is not None
            assert not telegram_client.session.closed

    @pytest.mark.asyncio
    async def test_context_manager_closes_session(self, telegram_client):
        """Test that exiting context closes aiohttp session."""
        async with telegram_client:
            session = telegram_client.session
        assert session.closed


class TestTelegramClientSendChatAction:
    """Tests for send_chat_action method."""

    @pytest.mark.asyncio
    async def test_send_chat_action_success(self, telegram_client):
        """Test successful sending of chat action."""
        telegram_client._make_request = AsyncMock(return_value=True)

        result = await telegram_client.send_chat_action(12345, "typing")

        assert result is True
        telegram_client._make_request.assert_called_once_with(
            "sendChatAction", json={"chat_id": 12345, "action": "typing"}
        )

    @pytest.mark.asyncio
    async def test_send_chat_action_default_typing(self, telegram_client):
        """Test that default action is 'typing'."""
        telegram_client._make_request = AsyncMock(return_value=True)

        result = await telegram_client.send_chat_action(12345)

        assert result is True
        telegram_client._make_request.assert_called_once_with(
            "sendChatAction", json={"chat_id": 12345, "action": "typing"}
        )

    @pytest.mark.asyncio
    async def test_send_chat_action_failure_returns_false(self, telegram_client):
        """Test that failure returns False without raising exception."""
        telegram_client._make_request = AsyncMock(side_effect=Exception("API error"))

        result = await telegram_client.send_chat_action(12345, "typing")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_chat_action_custom_action(self, telegram_client):
        """Test sending custom action type."""
        telegram_client._make_request = AsyncMock(return_value=True)

        result = await telegram_client.send_chat_action(12345, "upload_document")

        assert result is True
        telegram_client._make_request.assert_called_once_with(
            "sendChatAction", json={"chat_id": 12345, "action": "upload_document"}
        )


class TestTelegramClientMakeRequest:
    """Tests for _make_request method."""

    @pytest.mark.asyncio
    async def test_make_request_without_session_raises(self, telegram_client):
        """Test that making request without session raises error."""
        with pytest.raises(RuntimeError, match="Session is not initialized"):
            await telegram_client._make_request("sendMessage", json={})

    @pytest.mark.asyncio
    async def test_make_request_success(self, telegram_client):
        """Test successful API request."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"ok": True, "result": {"test": 1}})
        mock_response.raise_for_status = MagicMock()
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        telegram_client.session = mock_session

        result = await telegram_client._make_request("sendMessage", json={"test": 1})

        assert result == {"test": 1}

    @pytest.mark.asyncio
    async def test_make_request_api_error(self, telegram_client):
        """Test API error response raises ValueError."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"ok": False, "description": "Bad Request"}
        )
        mock_response.raise_for_status = MagicMock()
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        telegram_client.session = mock_session

        with pytest.raises(ValueError, match="Telegram API error: Bad Request"):
            await telegram_client._make_request("sendMessage", json={})
