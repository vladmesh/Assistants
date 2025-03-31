"""Tests for MessageQueue class."""
import pytest
import pytest_asyncio
import json
import os
from core.message_queue import MessageQueue
from config.settings import Settings

@pytest.fixture
def settings():
    """Create test settings."""
    settings = Settings()
    settings.INPUT_QUEUE = "test_input"
    settings.OUTPUT_QUEUE = "test_output"
    return settings

@pytest_asyncio.fixture
async def message_queue(settings):
    """Create MessageQueue instance with test Redis."""
    queue = MessageQueue(settings)
    yield queue
    # Cleanup
    await queue.redis.delete(settings.INPUT_QUEUE)
    await queue.redis.delete(settings.OUTPUT_QUEUE)
    await queue.close()

@pytest.mark.asyncio
async def test_get_message_success(message_queue, settings):
    """Test successful message retrieval."""
    # Setup
    test_message = {"message_id": "123", "text": "test"}
    await message_queue.redis.lpush(
        settings.INPUT_QUEUE,
        json.dumps(test_message)
    )
    
    # Execute
    result = await message_queue.get_message()
    
    # Verify
    assert result == test_message

@pytest.mark.asyncio
async def test_get_message_timeout(message_queue):
    """Test message retrieval timeout."""
    # Execute
    result = await message_queue.get_message(timeout=1)
    
    # Verify
    assert result is None

@pytest.mark.asyncio
async def test_get_message_invalid_json(message_queue, settings):
    """Test handling of invalid JSON message."""
    # Setup
    await message_queue.redis.lpush(settings.INPUT_QUEUE, "invalid json")
    
    # Execute and verify
    with pytest.raises(json.JSONDecodeError):
        await message_queue.get_message()

@pytest.mark.asyncio
async def test_send_response_success(message_queue, settings):
    """Test successful response sending."""
    # Setup
    test_response = {"message_id": "123", "text": "response"}
    
    # Execute
    await message_queue.send_response(test_response)
    
    # Verify
    result = await message_queue.redis.rpop(settings.OUTPUT_QUEUE)
    assert json.loads(result) == test_response

@pytest.mark.asyncio
async def test_multiple_messages(message_queue, settings):
    """Test handling multiple messages in sequence."""
    # Setup
    messages = [
        {"message_id": "1", "text": "first"},
        {"message_id": "2", "text": "second"},
        {"message_id": "3", "text": "third"}
    ]
    
    # Send messages in reverse order to match FIFO behavior
    for msg in reversed(messages):
        await message_queue.redis.lpush(settings.INPUT_QUEUE, json.dumps(msg))
    
    # Receive messages
    received = []
    for _ in range(len(messages)):
        msg = await message_queue.get_message()
        received.append(msg)
    
    # Verify - messages should be received in original order (FIFO)
    assert received == messages 