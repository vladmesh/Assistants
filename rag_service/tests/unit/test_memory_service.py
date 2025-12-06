"""Tests for Memory service."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
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
def memory_service(mock_openai_client):
    """Create MemoryService with mocked OpenAI."""
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
async def test_search_memories(memory_service, mock_openai_client):
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

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.return_value = mock_response_data
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        results = await memory_service.search_memories(
            query=query,
            user_id=user_id,
            limit=10,
        )

        assert len(results) == 1
        assert results[0]["text"] == "User likes pizza"


@pytest.mark.asyncio
async def test_create_memory(memory_service, mock_openai_client):
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

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.return_value = mock_response_data
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        memory = await memory_service.create_memory(
            user_id=user_id,
            text=text,
            memory_type=memory_type,
        )

        assert memory["text"] == text
        assert memory["memory_type"] == memory_type
