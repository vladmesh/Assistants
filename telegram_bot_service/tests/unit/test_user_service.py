# telegram_bot_service/tests/unit/test_user_service.py
"""Unit tests for user service functions."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


@pytest.fixture
def mock_rest_client():
    """Create mock REST client."""
    return AsyncMock()


@pytest.fixture
def mock_telegram_client():
    """Create mock Telegram client."""
    return AsyncMock()


class TestGetOrCreateTelegramUser:
    """Tests for get_or_create_telegram_user function."""

    @pytest.mark.asyncio
    async def test_success(self, mock_rest_client):
        """Test successful user retrieval/creation."""
        from shared_models.api_schemas import TelegramUserRead

        from services.user_service import get_or_create_telegram_user

        expected_user = MagicMock(spec=TelegramUserRead)
        expected_user.id = 1
        expected_user.telegram_id = 12345
        mock_rest_client.get_or_create_user = AsyncMock(return_value=expected_user)

        result = await get_or_create_telegram_user(
            mock_rest_client, telegram_id=12345, username="test_user"
        )

        assert result == expected_user
        mock_rest_client.get_or_create_user.assert_called_once_with(12345, "test_user")

    @pytest.mark.asyncio
    async def test_none_response_raises(self, mock_rest_client):
        """Test that None response raises RestClientError."""
        from clients.rest import RestClientError
        from services.user_service import get_or_create_telegram_user

        mock_rest_client.get_or_create_user = AsyncMock(return_value=None)

        with pytest.raises(RestClientError, match="unexpected None response"):
            await get_or_create_telegram_user(
                mock_rest_client, telegram_id=12345, username="test"
            )


class TestGetAssignedSecretary:
    """Tests for get_assigned_secretary function."""

    @pytest.mark.asyncio
    async def test_returns_secretary(self, mock_rest_client):
        """Test returning assigned secretary."""
        from shared_models.api_schemas import AssistantRead

        from services.user_service import get_assigned_secretary

        user_id = uuid4()
        secretary_id = uuid4()
        expected_secretary = MagicMock(spec=AssistantRead)
        expected_secretary.id = secretary_id
        expected_secretary.name = "Test Secretary"

        mock_rest_client.get_user_secretary = AsyncMock(return_value=expected_secretary)

        result = await get_assigned_secretary(mock_rest_client, user_id)

        assert result == expected_secretary
        mock_rest_client.get_user_secretary.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_returns_none_when_not_assigned(self, mock_rest_client):
        """Test returning None when no secretary assigned."""
        from services.user_service import get_assigned_secretary

        user_id = uuid4()
        mock_rest_client.get_user_secretary = AsyncMock(return_value=None)

        result = await get_assigned_secretary(mock_rest_client, user_id)

        assert result is None


class TestSetUserSecretary:
    """Tests for set_user_secretary function."""

    @pytest.mark.asyncio
    async def test_success(self, mock_rest_client):
        """Test successful secretary assignment."""
        from services.user_service import set_user_secretary

        user_id = uuid4()
        secretary_id = uuid4()
        mock_rest_client.set_user_secretary = AsyncMock()

        await set_user_secretary(mock_rest_client, user_id, secretary_id)

        mock_rest_client.set_user_secretary.assert_called_once_with(
            user_id, secretary_id
        )


class TestListAvailableSecretaries:
    """Tests for list_available_secretaries function."""

    @pytest.mark.asyncio
    async def test_returns_list(self, mock_rest_client):
        """Test returning list of secretaries."""

        from services.user_service import list_available_secretaries

        secretary_data = {
            "id": str(uuid4()),
            "name": "Secretary 1",
            "is_secretary": True,
            "model": "gpt-4",
            "assistant_type": "llm",
            "is_active": True,
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
            "tools": [],
        }

        mock_rest_client.list_secretaries = AsyncMock(return_value=[secretary_data])

        result = await list_available_secretaries(mock_rest_client)

        assert len(result) == 1
        mock_rest_client.list_secretaries.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_list(self, mock_rest_client):
        """Test empty secretaries list."""
        from services.user_service import list_available_secretaries

        mock_rest_client.list_secretaries = AsyncMock(return_value=[])

        result = await list_available_secretaries(mock_rest_client)

        assert result == []

    @pytest.mark.asyncio
    async def test_rest_error_propagates(self, mock_rest_client):
        """Test REST client error propagates."""
        from clients.rest import RestClientError
        from services.user_service import list_available_secretaries

        mock_rest_client.list_secretaries = AsyncMock(
            side_effect=RestClientError("Connection failed")
        )

        with pytest.raises(RestClientError):
            await list_available_secretaries(mock_rest_client)


class TestEscapeMarkdownV2:
    """Tests for escape_markdown_v2 function."""

    def test_escapes_special_chars(self):
        """Test that special characters are escaped."""
        from services.user_service import escape_markdown_v2

        text = "Hello_World*Test[1](2)~`code`>>#+-=|{}.!"
        result = escape_markdown_v2(text)

        # All special chars should be escaped with backslash
        assert "\\_" in result
        assert "\\*" in result
        assert "\\[" in result
        assert "\\]" in result
        assert "\\(" in result
        assert "\\)" in result
        assert "\\~" in result
        assert "\\`" in result
        assert "\\>" in result
        assert "\\#" in result
        assert "\\+" in result
        assert "\\-" in result
        assert "\\=" in result
        assert "\\|" in result
        assert "\\{" in result
        assert "\\}" in result
        assert "\\." in result
        assert "\\!" in result

    def test_plain_text_unchanged(self):
        """Test that plain text remains unchanged."""
        from services.user_service import escape_markdown_v2

        text = "Hello World 123"
        result = escape_markdown_v2(text)

        assert result == text


class TestPromptSecretarySelection:
    """Tests for prompt_secretary_selection function."""

    @pytest.mark.asyncio
    async def test_success(self, mock_rest_client, mock_telegram_client):
        """Test successful secretary selection prompt."""
        from shared_models.api_schemas import AssistantRead

        from services.user_service import prompt_secretary_selection

        secretary_id = uuid4()
        secretary_data = {
            "id": str(secretary_id),
            "name": "Test Secretary",
            "description": "A test secretary",
            "is_secretary": True,
            "model": "gpt-4",
            "assistant_type": "llm",
            "is_active": True,
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
            "tools": [],
        }
        # Validate that data is parseable (optional sanity check)
        AssistantRead(**secretary_data)

        mock_rest_client.list_secretaries = AsyncMock(return_value=[secretary_data])

        # Mock the keyboard creation
        with patch(
            "services.user_service.create_secretary_selection_keyboard"
        ) as mock_kb:
            mock_kb.return_value = [[{"text": "Test", "callback_data": "test"}]]

            result = await prompt_secretary_selection(
                mock_telegram_client,
                mock_rest_client,
                chat_id=12345,
                prompt_message="Choose secretary:",
            )

        assert result is True
        mock_telegram_client.send_message_with_inline_keyboard.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_secretaries_available(
        self, mock_rest_client, mock_telegram_client
    ):
        """Test handling when no secretaries available."""
        from services.user_service import prompt_secretary_selection

        mock_rest_client.list_secretaries = AsyncMock(return_value=[])

        result = await prompt_secretary_selection(
            mock_telegram_client,
            mock_rest_client,
            chat_id=12345,
            prompt_message="Choose secretary:",
        )

        assert result is False
        mock_telegram_client.send_message.assert_called_once()
        call_args = mock_telegram_client.send_message.call_args
        assert "нет доступных секретарей" in call_args[0][1].lower()

    @pytest.mark.asyncio
    async def test_rest_client_error(self, mock_rest_client, mock_telegram_client):
        """Test handling REST client error."""
        from clients.rest import RestClientError
        from services.user_service import prompt_secretary_selection

        mock_rest_client.list_secretaries = AsyncMock(
            side_effect=RestClientError("Failed")
        )

        result = await prompt_secretary_selection(
            mock_telegram_client,
            mock_rest_client,
            chat_id=12345,
            prompt_message="Choose secretary:",
        )

        assert result is False
        mock_telegram_client.send_message.assert_called_once()
