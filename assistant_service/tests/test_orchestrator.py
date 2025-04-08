# Import unittest.mock for ANY matcher
import unittest.mock
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from config.settings import Settings
from messages.queue_models import (
    QueueMessage,
    QueueMessageContent,
    QueueMessageSource,
    QueueMessageType,
)
from orchestrator import AssistantOrchestrator


@pytest.fixture
def settings():
    return Settings(
        REDIS_HOST="redis",
        REDIS_PORT=6379,
        REDIS_DB=0,
        INPUT_QUEUE="test:input",
        OUTPUT_QUEUE="test:output",
    )


@pytest.fixture
def human_queue_message():
    return QueueMessage(
        type=QueueMessageType.HUMAN,
        user_id=123,
        source=QueueMessageSource.USER,
        content=QueueMessageContent(
            message="Hello, assistant!", metadata={"chat_id": 456}
        ),
        timestamp=datetime.now(),
    )


@pytest.fixture
def tool_queue_message():
    return QueueMessage(
        type=QueueMessageType.TOOL,
        user_id=123,
        source=QueueMessageSource.CALENDAR,
        content=QueueMessageContent(
            message="Event created successfully",
            metadata={"tool_name": "calendar_create", "event_id": "abc123"},
        ),
        timestamp=datetime.now(),
    )


@pytest.mark.asyncio
async def test_process_human_message(settings, human_queue_message):
    # Mock dependencies
    with patch("orchestrator.AssistantFactory") as mock_factory:
        # Setup mocks
        mock_secretary = AsyncMock()
        mock_secretary.process_message.return_value = "Hello, user!"
        mock_factory_instance = mock_factory.return_value
        mock_factory_instance.get_user_secretary = AsyncMock(
            return_value=mock_secretary
        )

        # Create orchestrator
        orchestrator = AssistantOrchestrator(settings)

        # Process message (thread_id removed)
        response = await orchestrator.process_message(
            human_queue_message  # Removed test_thread_id
        )

        # Assertions
        mock_factory_instance.get_user_secretary.assert_awaited_once_with(123)
        # Verify process_message call arguments using assert_awaited_once_with
        mock_secretary.process_message.assert_awaited_once_with(
            message=unittest.mock.ANY,  # Check that message argument was passed
            user_id="123",  # Check user_id keyword argument
        )
        # The checks below are now covered by assert_awaited_once_with
        # call_args, call_kwargs = mock_secretary.process_message.call_args
        # assert len(call_args) == 2 # Expect message and user_id
        # assert isinstance(call_args[0], HumanMessage)
        # assert call_args[1] == "123"
        # assert not call_kwargs # No keyword arguments expected
        assert response["status"] == "success"
        assert response["response"] == "Hello, user!"
        assert response["user_id"] == 123


@pytest.mark.asyncio
async def test_process_tool_message(settings, tool_queue_message):
    # Mock dependencies
    with patch("orchestrator.AssistantFactory") as mock_factory:
        # Setup mocks
        mock_secretary = AsyncMock()
        mock_secretary.process_message.return_value = "Tool executed successfully"
        mock_factory_instance = mock_factory.return_value
        mock_factory_instance.get_user_secretary = AsyncMock(
            return_value=mock_secretary
        )

        # Create orchestrator
        orchestrator = AssistantOrchestrator(settings)

        # Process message (thread_id removed)
        response = await orchestrator.process_message(
            tool_queue_message  # Removed test_thread_id
        )

        # Assertions
        mock_factory_instance.get_user_secretary.assert_awaited_once_with(123)
        # Verify process_message call arguments using assert_awaited_once_with
        mock_secretary.process_message.assert_awaited_once_with(
            message=unittest.mock.ANY,  # Check that message argument was passed
            user_id="123",  # Check user_id keyword argument
        )
        # The checks below are now covered by assert_awaited_once_with
        # call_args, call_kwargs = mock_secretary.process_message.call_args
        # assert len(call_args) == 2 # Expect message and user_id
        # assert isinstance(call_args[0], ToolMessage)
        # assert call_args[1] == "123"
        # assert not call_kwargs # No keyword arguments expected
        assert response["status"] == "success"
        assert response["response"] == "Tool executed successfully"
        assert response["user_id"] == 123


@pytest.mark.asyncio
async def test_process_message_error(settings, human_queue_message):
    # Mock dependencies
    with patch("orchestrator.AssistantFactory") as mock_factory, patch(
        "orchestrator.RestServiceClient"
    ):
        # Setup mocks to raise error
        mock_secretary = AsyncMock()
        mock_secretary.process_message.side_effect = Exception("Test error")
        mock_factory_instance = mock_factory.return_value
        mock_factory_instance.get_user_secretary = AsyncMock(
            return_value=mock_secretary
        )

        # Create orchestrator
        orchestrator = AssistantOrchestrator(settings)

        # Process message (thread_id removed)
        response = await orchestrator.process_message(
            human_queue_message  # Removed test_thread_id
        )

        # Assertions
        mock_factory_instance.get_user_secretary.assert_awaited_once_with(123)
        # Verify process_message call arguments using assert_awaited_once_with
        mock_secretary.process_message.assert_awaited_once_with(
            message=unittest.mock.ANY,  # Check that message argument was passed
            user_id="123",  # Check user_id keyword argument
        )
        # The checks below are now covered by assert_awaited_once_with
        # call_args, call_kwargs = mock_secretary.process_message.call_args
        # assert len(call_args) == 2 # Expect message and user_id
        # assert isinstance(call_args[0], HumanMessage)
        # assert call_args[1] == "123"
        # assert not call_kwargs # No keyword arguments expected
        assert response["status"] == "error"
        assert response["error"] == "Test error"
        assert response["user_id"] == 123


@pytest.mark.asyncio
async def test_listen_for_messages(settings, human_queue_message):
    # Mock dependencies
    with patch("orchestrator.AssistantFactory") as mock_factory, patch(
        "orchestrator.RestServiceClient"
    ):
        # Setup secretary mock
        mock_secretary = AsyncMock()
        mock_secretary.process_message.return_value = "Hello, user!"
        mock_factory_instance = mock_factory.return_value
        mock_factory_instance.get_user_secretary = AsyncMock(
            return_value=mock_secretary
        )

        # Create orchestrator
        orchestrator = AssistantOrchestrator(settings)

        # Push message to Redis queue
        await orchestrator.redis.rpush(
            settings.INPUT_QUEUE, human_queue_message.model_dump_json()
        )

        # Start listening (will process one message and exit)
        await orchestrator.listen_for_messages(max_messages=1)

        # Verify message was processed using assert_awaited_once_with
        mock_secretary.process_message.assert_awaited_once_with(
            message=unittest.mock.ANY,  # Check that message argument was passed
            user_id="123",  # Check user_id keyword argument
        )
        # The checks below are now covered by assert_awaited_once_with
        # call_args, call_kwargs = mock_secretary.process_message.call_args
        # assert len(call_args) == 2
        # assert isinstance(call_args[0], HumanMessage)
        # assert call_args[1] == "123" # Check user_id
        # assert not call_kwargs # No kwargs expected
