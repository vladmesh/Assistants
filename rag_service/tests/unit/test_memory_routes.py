"""Tests for Memory API routes."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


@pytest.fixture
def mock_memory_service():
    """Mock MemoryService for route tests."""
    with patch("api.memory_routes.MemoryService") as mock:
        mock_instance = AsyncMock()
        mock.return_value = mock_instance
        yield mock_instance


def test_search_memories_endpoint(mock_memory_service):
    """Test memory search endpoint."""
    mock_memory_service.search_memories.return_value = [
        {
            "id": str(uuid4()),
            "user_id": 123,
            "text": "User likes pizza",
            "memory_type": "user_fact",
            "importance": 5,
        }
    ]

    response = client.post(
        "/api/memory/search",
        json={
            "query": "What do I like?",
            "user_id": 123,
            "limit": 10,
            "threshold": 0.7,
        },
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["text"] == "User likes pizza"


def test_create_memory_endpoint(mock_memory_service):
    """Test memory creation endpoint."""
    mock_memory_service.create_memory.return_value = {
        "id": str(uuid4()),
        "user_id": 123,
        "text": "User prefers dark mode",
        "memory_type": "preference",
        "importance": 1,
    }

    response = client.post(
        "/api/memory/",
        json={
            "user_id": 123,
            "text": "User prefers dark mode",
            "memory_type": "preference",
            "importance": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["text"] == "User prefers dark mode"
    assert response.json()["memory_type"] == "preference"
