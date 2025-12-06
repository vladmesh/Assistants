# rag_service/tests/unit/conftest.py
"""Unit test fixtures - mocks for external services."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client for vector DB tests."""
    with patch("src.services.vector_db_service.QdrantClient") as mock:
        mock_instance = MagicMock()
        mock_collections = MagicMock()
        mock_collections.collections = []
        mock_instance.get_collections.return_value = mock_collections
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for embedding generation."""
    with patch("src.services.memory_service.OpenAI") as mock:
        mock_instance = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1] * 1536
        mock_instance.embeddings.create.return_value = MagicMock(data=[mock_embedding])
        mock.return_value = mock_instance
        yield mock_instance
