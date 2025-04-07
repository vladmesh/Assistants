from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from config.settings import Settings
from langchain_core.messages import HumanMessage, ToolMessage
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

        # Process message
        response = await orchestrator.process_message(human_queue_message)

        # Verify response
        assert response["user_id"] == 123
        assert response["text"] == "Hello, assistant!"
        assert response["response"] == "Hello, user!"
        assert response["status"] == "success"
        assert response["source"] == QueueMessageSource.USER
        assert response["type"] == QueueMessageType.HUMAN
        assert "metadata" in response

        # Verify secretary was called with HumanMessage
        mock_secretary.process_message.assert_called_once()
        call_args = mock_secretary.process_message.call_args[0]
        assert isinstance(call_args[0], HumanMessage)


@pytest.mark.asyncio
async def test_process_tool_message(settings, tool_queue_message):
    # Mock dependencies
    with patch("orchestrator.AssistantFactory") as mock_factory, patch(
        "orchestrator.RestServiceClient"
    ) as mock_rest:
        # Setup mocks
        mock_secretary = AsyncMock()
        mock_secretary.process_message.return_value = "Tool executed successfully"
        mock_factory_instance = mock_factory.return_value
        mock_factory_instance.get_user_secretary = AsyncMock(
            return_value=mock_secretary
        )

        # Create orchestrator
        orchestrator = AssistantOrchestrator(settings)

        # Process message
        response = await orchestrator.process_message(tool_queue_message)

        # Verify response
        assert response["user_id"] == 123
        assert response["text"] == "Event created successfully"
        assert response["response"] == "Tool executed successfully"
        assert response["status"] == "success"
        assert response["source"] == QueueMessageSource.CALENDAR
        assert response["type"] == QueueMessageType.TOOL
        assert "metadata" in response

        # Verify secretary was called with ToolMessage
        mock_secretary.process_message.assert_called_once()
        call_args = mock_secretary.process_message.call_args[0]
        assert isinstance(call_args[0], ToolMessage)


@pytest.mark.asyncio
async def test_process_message_error(settings, human_queue_message):
    # Mock dependencies
    with patch("orchestrator.AssistantFactory") as mock_factory, patch(
        "orchestrator.RestServiceClient"
    ) as mock_rest:
        # Setup mocks to raise error
        mock_secretary = AsyncMock()
        mock_secretary.process_message.side_effect = Exception("Test error")
        mock_factory_instance = mock_factory.return_value
        mock_factory_instance.get_user_secretary = AsyncMock(
            return_value=mock_secretary
        )

        # Create orchestrator
        orchestrator = AssistantOrchestrator(settings)

        # Process message
        response = await orchestrator.process_message(human_queue_message)

        # Verify error response
        assert response["user_id"] == 123
        assert response["text"] == "Hello, assistant!"
        assert response["status"] == "error"
        assert "Test error" in response["error"]
        assert response["source"] == QueueMessageSource.USER
        assert response["type"] == QueueMessageType.HUMAN


@pytest.mark.asyncio
async def test_listen_for_messages(settings, human_queue_message):
    # Mock dependencies
    with patch("orchestrator.AssistantFactory") as mock_factory, patch(
        "orchestrator.RestServiceClient"
    ) as mock_rest:
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

        # Verify message was processed
        mock_secretary.process_message.assert_called_once()
        call_args = mock_secretary.process_message.call_args[0]
        assert isinstance(call_args[0], HumanMessage)
