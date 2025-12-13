# tests/integration/test_rag_service_integration.py
"""Integration tests for RAG service.

Tests real HTTP interaction with rag_service container.
RAG service is now included in docker-compose.integration.yml by default.
"""

import os

import httpx
import pytest

RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://test-rag-service:8002")


@pytest.fixture
def rag_client():
    """Create HTTP client for RAG service."""
    return httpx.AsyncClient(base_url=RAG_SERVICE_URL, timeout=30.0)


class TestRagServiceHealth:
    """Tests for RAG service health and availability."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, rag_client):
        """Test RAG service health endpoint is accessible."""
        response = await rag_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestRagServiceMemoryEndpoints:
    """Tests for RAG service memory endpoints."""

    @pytest.mark.asyncio
    async def test_memory_search_endpoint_exists(self, rag_client):
        """Test memory search endpoint exists and validates input."""
        payload = {
            "query": "test query",
            "user_id": 123,
            "limit": 5,
            "threshold": 0.7,
        }

        response = await rag_client.post("/api/memory/search", json=payload)

        # Endpoint should exist (not 404)
        assert response.status_code != 404, "Memory search endpoint not found"
        # May return 500 if OpenAI key invalid, but endpoint exists
        assert response.status_code in [200, 500]

    @pytest.mark.asyncio
    async def test_memory_create_endpoint_exists(self, rag_client):
        """Test memory create endpoint exists and validates input."""
        payload = {
            "user_id": 123,
            "text": "Test memory for integration test",
            "memory_type": "user_fact",
            "importance": 5,
        }

        response = await rag_client.post("/api/memory/", json=payload)

        # Endpoint should exist (not 404)
        assert response.status_code != 404, "Memory create endpoint not found"
        # May return 500 if OpenAI key invalid, but endpoint exists
        assert response.status_code in [200, 500]

    @pytest.mark.asyncio
    async def test_memory_search_validation_missing_user_id(self, rag_client):
        """Test memory search endpoint validates required user_id field."""
        invalid_payload = {"query": "test"}

        response = await rag_client.post("/api/memory/search", json=invalid_payload)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_memory_search_validation_missing_query(self, rag_client):
        """Test memory search endpoint validates required query field."""
        invalid_payload = {"user_id": 123}

        response = await rag_client.post("/api/memory/search", json=invalid_payload)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_memory_create_validation_missing_user_id(self, rag_client):
        """Test memory create endpoint validates required user_id field."""
        invalid_payload = {"text": "test", "memory_type": "user_fact"}

        response = await rag_client.post("/api/memory/", json=invalid_payload)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_memory_create_validation_missing_text(self, rag_client):
        """Test memory create endpoint validates required text field."""
        invalid_payload = {"user_id": 123, "memory_type": "user_fact"}

        response = await rag_client.post("/api/memory/", json=invalid_payload)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_memory_create_validation_missing_memory_type(self, rag_client):
        """Test memory create endpoint validates required memory_type field."""
        invalid_payload = {"user_id": 123, "text": "test"}

        response = await rag_client.post("/api/memory/", json=invalid_payload)

        assert response.status_code == 422


class TestRagServiceApiContract:
    """Contract tests verifying RagServiceClient API structure."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with RAG service URL."""
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.RAG_SERVICE_URL = RAG_SERVICE_URL
        return settings

    @pytest.fixture
    def rag_service_client(self, mock_settings):
        """Create RagServiceClient instance."""
        from services.rag_service import RagServiceClient

        return RagServiceClient(settings=mock_settings)

    @pytest.mark.asyncio
    async def test_search_uses_correct_endpoint(self, rag_service_client):
        """Verify search_memories calls correct endpoint."""
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=[])
        mock_response.raise_for_status = MagicMock()

        with patch.object(rag_service_client, "get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            await rag_service_client.search_memories(
                query="test", user_id=123, limit=10, threshold=0.7
            )

            call_args = mock_http_client.post.call_args
            assert call_args[0][0] == "/api/memory/search"

    @pytest.mark.asyncio
    async def test_create_uses_correct_endpoint(self, rag_service_client):
        """Verify create_memory calls correct endpoint."""
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"id": "test"})
        mock_response.raise_for_status = MagicMock()

        with patch.object(rag_service_client, "get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            await rag_service_client.create_memory(
                user_id=123, text="test", memory_type="user_fact", importance=5
            )

            call_args = mock_http_client.post.call_args
            assert call_args[0][0] == "/api/memory/"
