from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from shared_models import QueueMessage, QueueMessageSource
from shared_models.queue import QueueTrigger, TriggerType


@pytest.fixture
def human_queue_message():
    """Fixture for a user message."""
    return QueueMessage(
        user_id=123,
        content="Hello, assistant!",
        metadata={"chat_id": 456, "source": "telegram"},
        timestamp=datetime.now(UTC),
    )


@pytest.fixture
def reminder_trigger_event():
    """Fixture for a reminder trigger event message. Returns QueueTrigger."""
    return QueueTrigger(
        trigger_type=TriggerType.REMINDER,
        user_id=123,
        source=QueueMessageSource.CRON,
        payload={
            "reminder_id": "rem_abc789",
            "details": {"message": "Time for your meeting!"},
        },
    )


@pytest.fixture
def mock_factory(mocker):  # Use mocker fixture for patching
    """Mock AssistantFactory."""
    # Create a mock for the class itself to control instantiation
    mock_factory_class = MagicMock()

    # Mock the instance that the class constructor would return
    mock_factory_instance = AsyncMock()
    mock_secretary = AsyncMock()  # Mock secretary instance
    mock_secretary.process_message.return_value = "Mocked secretary response"
    mock_factory_instance.get_user_secretary.return_value = mock_secretary

    # Configure the class mock to return the instance mock
    mock_factory_class.return_value = mock_factory_instance

    # Patch the AssistantFactory where it's imported in orchestrator.py
    # Adjust the path 'assistant_service.src.orchestrator.AssistantFactory' if necessary
    mocker.patch("src.orchestrator.AssistantFactory", mock_factory_class)

    # Return the instance mock for use in tests
    return mock_factory_instance


# Fixture for mock_secretary if needed separately
@pytest.fixture
def mock_secretary(mock_factory):
    """Provides the mocked secretary instance from the mocked factory."""
    # The factory mock already creates and configures the secretary mock.
    # We retrieve it from the factory mock instance.
    return mock_factory.get_user_secretary.return_value
