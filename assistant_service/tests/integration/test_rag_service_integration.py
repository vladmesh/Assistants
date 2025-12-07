# tests/integration/test_rag_service_integration.py
"""Integration tests for RAG service.

Tests real HTTP interaction with rag_service container.
Run with: docker compose -f docker-compose.integration.yml --profile with-rag up
"""

import os

import httpx
import pytest

# Check if RAG service is available
RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://test-rag-service:8002")


def rag_service_available() -> bool:
    """Check if RAG service is reachable."""
    try:
        response = httpx.get(f"{RAG_SERVICE_URL}/health", timeout=2.0)
        return response.status_code == 200
    except Exception:
        return False


@pytest.fixture
def rag_http_client():
    """Create HTTP client for RAG service."""
    return httpx.AsyncClient(base_url=RAG_SERVICE_URL, timeout=30.0)


@pytest.mark.skipif(
    not rag_service_available(),
    reason="RAG service not available. Run with --profile with-rag",
)
class TestRagServiceRealIntegration:
    """Integration tests with real RAG service container."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, rag_http_client):
        """Test RAG service health endpoint is accessible."""
        response = await rag_http_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_memory_search_endpoint_exists(self, rag_http_client):
        """Test memory search endpoint accepts requests.

        Note: Will fail with 500 if OpenAI key not configured,
        but validates endpoint exists and accepts correct payload.
        """
        payload = {
            "query": "test query",
            "user_id": 123,
            "limit": 5,
            "threshold": 0.7,
        }

        response = await rag_http_client.post("/api/memory/search", json=payload)

        # Endpoint should exist (not 404)
        assert response.status_code != 404, "Memory search endpoint not found"

        # If OpenAI key is valid, should return 200
        # If not, will return 500 (expected in test environment)
        assert response.status_code in [200, 500]

    @pytest.mark.asyncio
    async def test_memory_create_endpoint_exists(self, rag_http_client):
        """Test memory create endpoint accepts requests."""
        payload = {
            "user_id": 123,
            "text": "Test memory for integration test",
            "memory_type": "user_fact",
            "importance": 5,
        }

        response = await rag_http_client.post("/api/memory/", json=payload)

        # Endpoint should exist (not 404)
        assert response.status_code != 404, "Memory create endpoint not found"

        # If OpenAI key is valid, should return 200
        # If not, will return 500 (expected in test environment)
        assert response.status_code in [200, 500]

    @pytest.mark.asyncio
    async def test_memory_search_validation(self, rag_http_client):
        """Test memory search endpoint validates payload."""
        # Missing required fields
        invalid_payload = {"query": "test"}

        response = await rag_http_client.post(
            "/api/memory/search", json=invalid_payload
        )

        # Should return 422 for validation error
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_memory_create_validation(self, rag_http_client):
        """Test memory create endpoint validates payload."""
        # Missing required fields
        invalid_payload = {"text": "test"}

        response = await rag_http_client.post("/api/memory/", json=invalid_payload)

        # Should return 422 for validation error
        assert response.status_code == 422


class TestRagServiceApiContract:
    """Contract tests verifying API structure (mocked, always run)."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with RAG service URL."""
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.RAG_SERVICE_URL = "http://rag-service:8002"
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
