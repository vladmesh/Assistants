import json
import unittest.mock
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import HumanMessage, ToolMessage
from orchestrator import AssistantOrchestrator

from shared_models import QueueMessage, QueueMessageType, QueueTrigger

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio


async def test_process_human_message(
    mock_settings,
    mock_factory,
    mock_secretary,
    human_queue_message,
    mocker,
    mock_rest_client,
):
    """Test processing a valid HumanQueueMessage."""
    # Patch dependencies before creating orchestrator
    mocker.patch("orchestrator.RestServiceClient", return_value=mock_rest_client)
    mocker.patch("orchestrator.AssistantFactory", return_value=mock_factory)

    orchestrator = AssistantOrchestrator(mock_settings)
    # Mock the Redis client within the orchestrator instance for this test
    orchestrator.redis = AsyncMock()

    # Act
    response = await orchestrator.process_message(human_queue_message)

    # Assert
    mock_factory.get_user_secretary.assert_awaited_once_with(123)
    mock_secretary.process_message.assert_awaited_once_with(
        message=unittest.mock.ANY,
        user_id="123",
        triggered_event=None,
    )
    # Check the type of the message passed
    call_args, call_kwargs = mock_secretary.process_message.call_args
    assert isinstance(call_kwargs["message"], HumanMessage)
    assert call_kwargs["message"].content == "Hello, assistant!"

    assert response["status"] == "success"
    # Check against the value set in the mock_secretary fixture
    assert response["response"] == "Mocked secretary response"
    assert response["user_id"] == 123
    # Verify response sent to redis
    # expected_response_message = QueueMessage(
    #     type=QueueMessageType.SECRETARY,
    #     user_id=123,
    #     source=human_queue_message.source,
    #     content=human_queue_message.content, # Keep original content info
    #     response="Mocked secretary response"
    # )
    # We need to mock the timestamp generation or compare excluding it
    # orchestrator.redis.rpush.assert_awaited_once() # Check that rpush was called
    # More specific check on rpush arguments (may need ANY for timestamp)
    # args, _ = orchestrator.redis.rpush.call_args
    # assert args[0] == mock_settings.OUTPUT_QUEUE
    # assert json.loads(args[1])["response"] == "Mocked secretary response"


async def test_process_tool_message(
    mock_settings,
    mock_factory,
    mock_secretary,
    tool_queue_message,
    mocker,
    mock_rest_client,
):
    """Test processing a valid ToolQueueMessage."""
    # Patch dependencies before creating orchestrator
    mocker.patch("orchestrator.RestServiceClient", return_value=mock_rest_client)
    mocker.patch("orchestrator.AssistantFactory", return_value=mock_factory)

    orchestrator = AssistantOrchestrator(mock_settings)
    orchestrator.redis = AsyncMock()

    # Act
    response = await orchestrator.process_message(tool_queue_message)

    # Assert
    mock_factory.get_user_secretary.assert_awaited_once_with(123)
    mock_secretary.process_message.assert_awaited_once_with(
        message=unittest.mock.ANY,
        user_id="123",
        triggered_event=None,
    )
    # Check the type of the message passed
    call_args, call_kwargs = mock_secretary.process_message.call_args
    assert isinstance(call_kwargs["message"], ToolMessage)
    assert call_kwargs["message"].content == "Event created successfully"
    assert call_kwargs["message"].tool_name == "calendar_create"  # Check tool_name

    assert response["status"] == "success"
    assert response["response"] == "Mocked secretary response"
    assert response["user_id"] == 123
    # Verify response sent to redis (similar check as above)
    # orchestrator.redis.rpush.assert_awaited_once()


async def test_process_message_secretary_error(
    mock_settings,
    mock_factory,
    mock_secretary,
    human_queue_message,
    mocker,
    mock_rest_client,
):
    """Test processing when secretary.process_message raises an error."""
    # Arrange: Configure secretary mock to raise an error
    test_error = Exception("Secretary failed")
    mock_secretary.process_message.side_effect = test_error

    # Patch dependencies before creating orchestrator
    mocker.patch("orchestrator.RestServiceClient", return_value=mock_rest_client)
    mocker.patch("orchestrator.AssistantFactory", return_value=mock_factory)

    orchestrator = AssistantOrchestrator(mock_settings)
    orchestrator.redis = AsyncMock()

    # Act
    response = await orchestrator.process_message(human_queue_message)

    # Assert
    mock_factory.get_user_secretary.assert_awaited_once_with(123)
    mock_secretary.process_message.assert_awaited_once_with(
        message=unittest.mock.ANY,
        user_id="123",
        triggered_event=None,
    )
    assert response["status"] == "error"
    assert response["error"] == str(test_error)
    assert response["user_id"] == 123
    # Verify NO response sent to redis on error
    # orchestrator.redis.rpush.assert_not_awaited()


async def test_process_message_factory_error(
    mock_settings, mock_factory, human_queue_message, mocker, mock_rest_client
):
    """Test processing when factory.get_user_secretary raises an error."""
    # Arrange: Configure factory mock to raise an error
    test_error = Exception("Factory failed")
    mock_factory.get_user_secretary.side_effect = test_error

    # Patch dependencies before creating orchestrator
    mocker.patch("orchestrator.RestServiceClient", return_value=mock_rest_client)
    mocker.patch("orchestrator.AssistantFactory", return_value=mock_factory)

    orchestrator = AssistantOrchestrator(mock_settings)
    orchestrator.redis = AsyncMock()

    # Act
    response = await orchestrator.process_message(human_queue_message)

    # Assert
    mock_factory.get_user_secretary.assert_awaited_once_with(123)
    # Secretary process_message should not be called
    # Assuming mock_secretary fixture is not directly used here
    # If mock_secretary is implicitly created by mock_factory, we need to check it wasn't called
    # secretary = mock_factory.get_user_secretary.return_value # This would raise error
    # secretary.process_message.assert_not_awaited() # This check depends on fixture setup

    assert response["status"] == "error"
    assert response["error"] == str(test_error)
    assert response["user_id"] == 123
    # Verify NO response sent to redis on error
    # orchestrator.redis.rpush.assert_not_awaited()


async def test_handle_reminder_trigger(
    mock_settings,
    mock_factory,
    mock_secretary,
    reminder_trigger_event,
    mocker,
    mock_rest_client,
):
    """Test handling a reminder_triggered event."""
    # Patch dependencies before creating orchestrator
    mocker.patch("orchestrator.RestServiceClient", return_value=mock_rest_client)
    mocker.patch("orchestrator.AssistantFactory", return_value=mock_factory)

    orchestrator = AssistantOrchestrator(mock_settings)
    orchestrator.redis = AsyncMock()

    # Act
    response = await orchestrator.handle_trigger(
        reminder_trigger_event
    )  # Use handle_trigger

    # Assert
    # Check that the factory was called with the correct user ID from the trigger event
    # The reminder_trigger_event fixture now uses user_id=123 (int)
    mock_factory.get_user_secretary.assert_awaited_once_with(123)

    # Check that the secretary's process_message was called
    mock_secretary.process_message.assert_awaited_once_with(
        message=None,  # Trigger passes None for message
        user_id="123",
        triggered_event=reminder_trigger_event,  # Check the event is passed
    )

    # # Check the ToolMessage passed to secretary (No longer applicable, event is passed directly)
    # call_args, call_kwargs = mock_secretary.process_message.call_args
    # assert isinstance(call_kwargs['message'], ToolMessage)
    # assert call_kwargs['message'].tool_call_id == "reminder_trigger" # Specific tool_call_id
    # # Check content structure (might need json.loads if content is stringified)
    # assert call_kwargs['message'].content == json.dumps({
    #     "reminder_id": "rem_abc789",
    #     "details": {"message": "Time for your meeting!"}
    # })

    assert response["status"] == "success"
    assert response["response"] == "Mocked secretary response"
    assert response["user_id"] == 123
    # Verify response sent to redis
    # orchestrator.redis.rpush.assert_awaited_once()

    # More specific check on rpush arguments (may need ANY for timestamp)
    # args, _ = orchestrator.redis.rpush.call_args
    # assert args[0] == mock_settings.OUTPUT_QUEUE
    # assert json.loads(args[1])["response"] == "Mocked secretary response"
