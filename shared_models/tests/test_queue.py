from datetime import datetime

from shared_models import (
    HumanQueueMessage,
    QueueMessage,
    QueueMessageContent,
    QueueMessageSource,
    QueueMessageType,
    ToolQueueMessage,
)


def test_queue_message_creation():
    """Test basic QueueMessage creation"""
    content = QueueMessageContent(message="test message", metadata={"key": "value"})
    message = QueueMessage(
        type=QueueMessageType.TOOL,
        user_id=1,
        source=QueueMessageSource.USER,
        content=content,
    )

    assert message.type == QueueMessageType.TOOL
    assert message.user_id == 1
    assert message.source == QueueMessageSource.USER
    assert message.content.message == "test message"
    assert message.content.metadata == {"key": "value"}
    assert isinstance(message.timestamp, datetime)


def test_tool_queue_message():
    """Test ToolQueueMessage creation"""
    content = QueueMessageContent(message="tool message")
    message = ToolQueueMessage(
        user_id=1,
        source=QueueMessageSource.USER,
        content=content,
        tool_name="test_tool",
    )

    assert message.type == QueueMessageType.TOOL
    assert message.tool_name == "test_tool"


def test_human_queue_message():
    """Test HumanQueueMessage creation"""
    content = QueueMessageContent(message="human message")
    message = HumanQueueMessage(
        user_id=1,
        source=QueueMessageSource.USER,
        content=content,
        chat_id=123456,
    )

    assert message.type == QueueMessageType.HUMAN
    assert message.chat_id == 123456


def test_queue_message_serialization():
    """Test QueueMessage serialization/deserialization"""
    content = QueueMessageContent(message="test message")
    original = QueueMessage(
        type=QueueMessageType.TOOL,
        user_id=1,
        source=QueueMessageSource.USER,
        content=content,
    )

    data = original.to_dict()
    restored = QueueMessage.from_dict(data)

    assert restored == original
