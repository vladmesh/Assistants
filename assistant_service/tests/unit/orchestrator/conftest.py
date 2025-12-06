from datetime import UTC, datetime
from unittest.mock import AsyncMock

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
def mock_factory(mocker):
    """Mock AssistantFactory."""
    mock_factory_instance = AsyncMock()
    mock_secretary = AsyncMock()
    mock_secretary.process_message.return_value = "Mocked secretary response"
    mock_factory_instance.get_user_secretary.return_value = mock_secretary
    return mock_factory_instance


@pytest.fixture
def mock_secretary(mock_factory):
    """Provides the mocked secretary instance from the mocked factory."""
    return mock_factory.get_user_secretary.return_value
