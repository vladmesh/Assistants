import pytest

from shared_models import (
    QueueMessage,
    QueueMessageContent,
    QueueMessageSource,
    QueueMessageType,
)


@pytest.fixture
def queue_message():
    """Fixture for basic QueueMessage"""
    content = QueueMessageContent(message="test message", metadata={"key": "value"})
    return QueueMessage(
        type=QueueMessageType.TOOL,
        user_id=1,
        source=QueueMessageSource.USER,
        content=content,
    )
