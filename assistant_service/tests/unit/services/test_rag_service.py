# tests/unit/services/test_rag_service.py
"""Unit tests for RagServiceClient."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import httpx
import pytest


class TestRagServiceClient:
    """Tests for RagServiceClient."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with RAG service URL."""
        settings = MagicMock()
        settings.RAG_SERVICE_URL = "http://rag-service:8002"
        return settings

    @pytest.fixture
    def client(self, mock_settings):
        """Create RagServiceClient instance."""
        # Import here to avoid any potential circular import issues
        from services.rag_service import RagServiceClient

        return RagServiceClient(settings=mock_settings)

    def test_init(self, client, mock_settings):
        """Test client initialization."""
        assert client.settings == mock_settings
        assert client._client is None

    def test_base_url(self, client):
        """Test base_url property."""
        assert client.base_url == "http://rag-service:8002"

    def test_get_client_lazy_init(self, client):
        """Test that httpx client is lazily initialized."""
        assert client._client is None
        http_client = client.get_client()
        assert http_client is not None
        assert client._client is http_client

        # Second call should return the same client
        same_client = client.get_client()
        assert same_client is http_client

    @pytest.mark.asyncio
    async def test_close(self, client):
        """Test closing the client."""
        # Initialize the client first
        _ = client.get_client()
        assert client._client is not None

        with patch.object(
            client._client, "aclose", new_callable=AsyncMock
        ) as mock_close:
            await client.close()
            mock_close.assert_called_once()

        assert client._client is None

    @pytest.mark.asyncio
    async def test_search_memories_success(self, client):
        """Test successful memory search."""
        mock_results = [
            {"text": "User likes Python", "memory_type": "user_fact", "score": 0.95},
            {
                "text": "User prefers dark mode",
                "memory_type": "preference",
                "score": 0.87,
            },
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=mock_results)
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            results = await client.search_memories(
                query="What does user like?",
                user_id=123,
                limit=10,
                threshold=0.7,
            )

            assert results == mock_results
            mock_http_client.post.assert_called_once_with(
                "/api/memory/search",
                json={
                    "query": "What does user like?",
                    "user_id": 123,
                    "limit": 10,
                    "threshold": 0.7,
                },
            )

    @pytest.mark.asyncio
    async def test_search_memories_http_error(self, client):
        """Test search memories with HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Error",
                request=MagicMock(),
                response=mock_response,
            )
        )

        with patch.object(client, "get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            with pytest.raises(httpx.HTTPStatusError):
                await client.search_memories(
                    query="Test query",
                    user_id=123,
                )

    @pytest.mark.asyncio
    async def test_search_memories_network_error(self, client):
        """Test search memories with network error."""
        with patch.object(client, "get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(
                side_effect=httpx.RequestError("Connection failed")
            )
            mock_get_client.return_value = mock_http_client

            with pytest.raises(httpx.RequestError):
                await client.search_memories(
                    query="Test query",
                    user_id=123,
                )

    @pytest.mark.asyncio
    async def test_create_memory_success(self, client):
        """Test successful memory creation."""
        mock_memory = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "user_id": 123,
            "text": "User likes Python programming",
            "memory_type": "user_fact",
            "importance": 7,
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=mock_memory)
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.create_memory(
                user_id=123,
                text="User likes Python programming",
                memory_type="user_fact",
                importance=7,
            )

            assert result == mock_memory
            mock_http_client.post.assert_called_once_with(
                "/api/memory/",
                json={
                    "user_id": 123,
                    "text": "User likes Python programming",
                    "memory_type": "user_fact",
                    "importance": 7,
                },
            )

    @pytest.mark.asyncio
    async def test_create_memory_with_assistant_id(self, client):
        """Test memory creation with assistant_id."""
        assistant_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        mock_memory = {
            "id": "660e8400-e29b-41d4-a716-446655440000",
            "user_id": 123,
            "text": "Test memory",
            "memory_type": "user_fact",
            "assistant_id": str(assistant_id),
            "importance": 5,
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=mock_memory)
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.create_memory(
                user_id=123,
                text="Test memory",
                memory_type="user_fact",
                assistant_id=assistant_id,
                importance=5,
            )

            assert result == mock_memory
            mock_http_client.post.assert_called_once_with(
                "/api/memory/",
                json={
                    "user_id": 123,
                    "text": "Test memory",
                    "memory_type": "user_fact",
                    "importance": 5,
                    "assistant_id": str(assistant_id),
                },
            )

    @pytest.mark.asyncio
    async def test_create_memory_http_error(self, client):
        """Test create memory with HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.text = "Validation Error"
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Error",
                request=MagicMock(),
                response=mock_response,
            )
        )

        with patch.object(client, "get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            with pytest.raises(httpx.HTTPStatusError):
                await client.create_memory(
                    user_id=123,
                    text="Test memory",
                    memory_type="user_fact",
                )

    @pytest.mark.asyncio
    async def test_create_memory_network_error(self, client):
        """Test create memory with network error."""
        with patch.object(client, "get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(
                side_effect=httpx.RequestError("Connection failed")
            )
            mock_get_client.return_value = mock_http_client

            with pytest.raises(httpx.RequestError):
                await client.create_memory(
                    user_id=123,
                    text="Test memory",
                    memory_type="user_fact",
                )
