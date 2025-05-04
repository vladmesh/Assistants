import json
import unittest.mock
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import HumanMessage
from orchestrator import AssistantOrchestrator

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio


async def test_dispatch_human_message(
    mock_settings,
    mock_factory,
    mock_secretary,
    human_queue_message,
    mocker,
    mock_rest_client,
):
    """Test dispatching a valid user message (QueueMessage)."""
    # Patch dependencies before creating orchestrator
    mocker.patch("orchestrator.RestServiceClient", return_value=mock_rest_client)
    mocker.patch("orchestrator.AssistantFactory", return_value=mock_factory)

    orchestrator = AssistantOrchestrator(mock_settings)
    # Mock the Redis client within the orchestrator instance for this test
    orchestrator.redis = AsyncMock()

    # Act - Use _dispatch_event
    response = await orchestrator._dispatch_event(human_queue_message)

    # Assert
    mock_factory.get_user_secretary.assert_awaited_once_with(123)
    # Check the call to secretary.process_message - no triggered_event
    mock_secretary.process_message.assert_awaited_once_with(
        message=unittest.mock.ANY,
        user_id="123",
        # triggered_event=None, # Removed assertion
    )
    # Check the type and content of the message passed
    call_args, call_kwargs = mock_secretary.process_message.call_args
    assert isinstance(call_kwargs["message"], HumanMessage)
    expected_timestamp = human_queue_message.timestamp
    expected_content = (
        f"(Sent at UTC: {expected_timestamp.isoformat()}) {human_queue_message.content}"
    )
    assert call_kwargs["message"].content == expected_content
    # Check metadata added by orchestrator
    assert call_kwargs["message"].metadata["source"] == "telegram"
    assert "timestamp" in call_kwargs["message"].metadata
    assert call_kwargs["message"].metadata["chat_id"] == 456  # Metadata from fixture

    assert response["status"] == "success"
    assert response["response"] == "Mocked secretary response"
    assert response["user_id"] == 123
    # orchestrator.redis.rpush assertions remain commented out


# Removed test_process_tool_message as QueueMessage is no longer used for TOOL type


async def test_dispatch_event_secretary_error(
    mock_settings,
    mock_factory,
    mock_secretary,
    human_queue_message,
    mocker,
    mock_rest_client,
):
    """Test dispatching when secretary.process_message raises an error."""
    # Arrange: Configure secretary mock to raise an error
    test_error = Exception("Secretary failed")
    mock_secretary.process_message.side_effect = test_error

    # Patch dependencies before creating orchestrator
    mocker.patch("orchestrator.RestServiceClient", return_value=mock_rest_client)
    mocker.patch("orchestrator.AssistantFactory", return_value=mock_factory)

    orchestrator = AssistantOrchestrator(mock_settings)
    orchestrator.redis = AsyncMock()

    # Act - Use _dispatch_event
    response = await orchestrator._dispatch_event(human_queue_message)

    # Assert
    mock_factory.get_user_secretary.assert_awaited_once_with(123)
    # Check the call to secretary.process_message - no triggered_event
    mock_secretary.process_message.assert_awaited_once_with(
        message=unittest.mock.ANY,
        user_id="123",
        # triggered_event=None, # Removed assertion
    )
    assert response["status"] == "error"
    assert response["error"] == str(test_error)
    assert response["user_id"] == 123
    # orchestrator.redis.rpush assertions remain commented out


async def test_dispatch_event_factory_error(
    mock_settings, mock_factory, human_queue_message, mocker, mock_rest_client
):
    """Test dispatching when factory.get_user_secretary raises an error."""
    # Arrange: Configure factory mock to raise an error
    test_error = Exception("Factory failed")
    mock_factory.get_user_secretary.side_effect = test_error

    # Patch dependencies before creating orchestrator
    mocker.patch("orchestrator.RestServiceClient", return_value=mock_rest_client)
    mocker.patch("orchestrator.AssistantFactory", return_value=mock_factory)

    orchestrator = AssistantOrchestrator(mock_settings)
    orchestrator.redis = AsyncMock()

    # Act - Use _dispatch_event
    response = await orchestrator._dispatch_event(human_queue_message)

    # Assert
    mock_factory.get_user_secretary.assert_awaited_once_with(123)
    # Secretary process_message should not be called
    mock_secretary = (
        mock_factory.get_user_secretary.return_value
    )  # Get the mock secretary
    mock_secretary.process_message.assert_not_awaited()  # Check it wasn't called

    assert response["status"] == "error"
    assert response["error"] == str(test_error)
    assert response["user_id"] == 123
    # orchestrator.redis.rpush assertions remain commented out


async def test_dispatch_reminder_trigger(
    mock_settings,
    mock_factory,
    mock_secretary,
    reminder_trigger_event,
    mocker,
    mock_rest_client,
):
    """Test dispatching a reminder_triggered event (QueueTrigger)."""
    # Patch dependencies before creating orchestrator
    mocker.patch("orchestrator.RestServiceClient", return_value=mock_rest_client)
    mocker.patch("orchestrator.AssistantFactory", return_value=mock_factory)

    orchestrator = AssistantOrchestrator(mock_settings)
    orchestrator.redis = AsyncMock()

    # Act - Use _dispatch_event
    response = await orchestrator._dispatch_event(reminder_trigger_event)

    # Assert
    mock_factory.get_user_secretary.assert_awaited_once_with(123)

    # Check that the secretary's process_message was called with correct args
    mock_secretary.process_message.assert_awaited_once_with(
        message=unittest.mock.ANY,
        user_id="123",
        # triggered_event=reminder_trigger_event, # Removed assertion
    )

    # Check the HumanMessage passed to secretary
    call_args, call_kwargs = mock_secretary.process_message.call_args
    passed_message = call_kwargs["message"]
    assert isinstance(passed_message, HumanMessage)

    # Verify content structure created by _dispatch_event
    expected_timestamp = reminder_trigger_event.timestamp
    expected_payload_json = json.dumps(reminder_trigger_event.payload)
    expected_content = f"System Trigger Activated:\nTimestamp UTC: {expected_timestamp.isoformat()}\nType: {reminder_trigger_event.trigger_type.value}\nSource: {reminder_trigger_event.source.value}\nPayload: {expected_payload_json}"
    assert passed_message.content == expected_content

    # Verify metadata
    assert passed_message.metadata["source"] == "cron"  # From QueueMessageSource.CRON
    assert passed_message.metadata["is_trigger"] is True
    assert "timestamp" in passed_message.metadata

    assert response["status"] == "success"
    assert response["response"] == "Mocked secretary response"
    assert response["user_id"] == 123
    # orchestrator.redis.rpush assertions remain commented out
