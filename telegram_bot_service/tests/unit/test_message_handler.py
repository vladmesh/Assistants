# telegram_bot_service/tests/unit/test_message_handler.py
"""Unit tests for message text handler."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


@pytest.fixture
def mock_telegram_client():
    """Mock TelegramClient."""
    client = MagicMock()
    client.send_message = AsyncMock()
    client.send_chat_action = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_rest_client():
    """Mock RestClient."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_user():
    """Mock TelegramUserRead."""
    user = MagicMock()
    user.id = 1
    user.telegram_id = 12345
    user.username = "test_user"
    return user


@pytest.fixture
def mock_secretary():
    """Mock AssistantRead."""
    secretary = MagicMock()
    secretary.id = uuid4()
    secretary.name = "Test Secretary"
    return secretary


class TestHandleTextMessageTypingAction:
    """Tests for typing action in handle_text_message."""

    @pytest.mark.asyncio
    async def test_sends_typing_action_before_queue(
        self, mock_telegram_client, mock_rest_client, mock_user, mock_secretary
    ):
        """Test that typing action is sent before sending message to queue."""
        with (
            patch(
                "handlers.message_text.user_service.get_user_by_telegram_id",
                new_callable=AsyncMock,
                return_value=mock_user,
            ),
            patch(
                "handlers.message_text.user_service.get_assigned_secretary",
                new_callable=AsyncMock,
                return_value=mock_secretary,
            ),
            patch(
                "handlers.message_text.message_queue.send_message_to_assistant",
                new_callable=AsyncMock,
            ) as mock_send_message,
        ):
            from handlers.message_text import handle_text_message

            context = {
                "telegram": mock_telegram_client,
                "rest": mock_rest_client,
                "chat_id": 12345,
                "user_id_str": "12345",
                "username": "test_user",
                "text": "Hello, assistant!",
            }

            await handle_text_message(**context)

            # Verify typing action was called
            mock_telegram_client.send_chat_action.assert_called_once_with(
                12345, "typing"
            )
            # Verify message was sent to queue
            mock_send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_typing_action_called_before_queue_message(
        self, mock_telegram_client, mock_rest_client, mock_user, mock_secretary
    ):
        """Test that typing action is called before queue message (order check)."""
        call_order = []

        async def track_typing(*args, **kwargs):
            call_order.append("typing")
            return True

        async def track_queue(*args, **kwargs):
            call_order.append("queue")

        mock_telegram_client.send_chat_action = track_typing

        with (
            patch(
                "handlers.message_text.user_service.get_user_by_telegram_id",
                new_callable=AsyncMock,
                return_value=mock_user,
            ),
            patch(
                "handlers.message_text.user_service.get_assigned_secretary",
                new_callable=AsyncMock,
                return_value=mock_secretary,
            ),
            patch(
                "handlers.message_text.message_queue.send_message_to_assistant",
                side_effect=track_queue,
            ),
        ):
            from handlers.message_text import handle_text_message

            context = {
                "telegram": mock_telegram_client,
                "rest": mock_rest_client,
                "chat_id": 12345,
                "user_id_str": "12345",
                "username": "test_user",
                "text": "Hello!",
            }

            await handle_text_message(**context)

            assert call_order == ["typing", "queue"]

    @pytest.mark.asyncio
    async def test_no_typing_action_when_user_not_found(
        self, mock_telegram_client, mock_rest_client
    ):
        """Test that typing action is NOT sent when user doesn't exist."""
        with patch(
            "handlers.message_text.user_service.get_user_by_telegram_id",
            new_callable=AsyncMock,
            return_value=None,
        ):
            from handlers.message_text import handle_text_message

            context = {
                "telegram": mock_telegram_client,
                "rest": mock_rest_client,
                "chat_id": 12345,
                "user_id_str": "12345",
                "username": "test_user",
                "text": "Hello!",
            }

            await handle_text_message(**context)

            # Typing action should NOT be called
            mock_telegram_client.send_chat_action.assert_not_called()
            # But send_message should be called to prompt /start
            mock_telegram_client.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_typing_action_when_no_secretary_assigned(
        self, mock_telegram_client, mock_rest_client, mock_user
    ):
        """Test that typing action is NOT sent when no secretary is assigned."""
        with (
            patch(
                "handlers.message_text.user_service.get_user_by_telegram_id",
                new_callable=AsyncMock,
                return_value=mock_user,
            ),
            patch(
                "handlers.message_text.user_service.get_assigned_secretary",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "handlers.message_text.user_service.prompt_secretary_selection",
                new_callable=AsyncMock,
            ),
        ):
            from handlers.message_text import handle_text_message

            context = {
                "telegram": mock_telegram_client,
                "rest": mock_rest_client,
                "chat_id": 12345,
                "user_id_str": "12345",
                "username": "test_user",
                "text": "Hello!",
            }

            await handle_text_message(**context)

            # Typing action should NOT be called
            mock_telegram_client.send_chat_action.assert_not_called()
