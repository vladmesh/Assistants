"""Tests for Memory service."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from services.memory_service import MemoryService


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for embedding generation."""
    with patch("services.memory_service.OpenAI") as mock:
        mock_instance = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1] * 1536
        mock_instance.embeddings.create.return_value = MagicMock(data=[mock_embedding])
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_rest_client():
    """Mock REST client for memory operations."""
    with patch("services.memory_service.get_rest_client") as mock:
        mock_client = MagicMock()
        mock_client.search_memories = AsyncMock()
        mock_client.create_memory = AsyncMock()
        mock.return_value = mock_client
        yield mock_client


@pytest.fixture
def memory_service(mock_openai_client, mock_rest_client):
    """Create MemoryService with mocked dependencies."""
    return MemoryService()


@pytest.mark.asyncio
async def test_generate_embedding(memory_service, mock_openai_client):
    """Test embedding generation."""
    text = "Test text for embedding"

    embedding = await memory_service.generate_embedding(text)

    mock_openai_client.embeddings.create.assert_called_once()
    assert len(embedding) == 1536
    assert all(isinstance(x, float) for x in embedding)


@pytest.mark.asyncio
async def test_search_memories(memory_service, mock_openai_client, mock_rest_client):
    """Test memory search."""
    query = "What do I like?"
    user_id = 123

    mock_response_data = [
        {
            "id": str(uuid4()),
            "user_id": user_id,
            "text": "User likes pizza",
            "memory_type": "user_fact",
            "importance": 5,
        }
    ]
    mock_rest_client.search_memories.return_value = mock_response_data

    results = await memory_service.search_memories(
        query=query,
        user_id=user_id,
        limit=10,
    )

    assert len(results) == 1
    assert results[0]["text"] == "User likes pizza"
    mock_rest_client.search_memories.assert_called_once()


@pytest.mark.asyncio
async def test_create_memory(memory_service, mock_openai_client, mock_rest_client):
    """Test memory creation."""
    user_id = 123
    text = "User prefers dark mode"
    memory_type = "preference"

    mock_response_data = {
        "id": str(uuid4()),
        "user_id": user_id,
        "text": text,
        "memory_type": memory_type,
        "importance": 1,
    }
    mock_rest_client.create_memory.return_value = mock_response_data

    memory = await memory_service.create_memory(
        user_id=user_id,
        text=text,
        memory_type=memory_type,
    )

    assert memory["text"] == text
    assert memory["memory_type"] == memory_type
    mock_rest_client.create_memory.assert_called_once()
