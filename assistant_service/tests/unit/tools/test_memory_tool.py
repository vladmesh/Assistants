# tests/unit/tools/test_memory_tool.py
"""Unit tests for Memory V2 tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


class TestMemorySaveTool:
    """Tests for MemorySaveTool."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with RAG service URL."""
        settings = MagicMock()
        settings.RAG_SERVICE_URL = "http://rag-service:8002"
        return settings

    @pytest.fixture
    def save_tool(self, mock_settings):
        """Create MemorySaveTool instance with mocked settings."""
        # Import here to avoid circular import issues during test collection
        from tools.memory_tool import MemorySaveTool

        return MemorySaveTool(
            name="save_memory",
            description="Save a memory",
            settings=mock_settings,
            user_id="123",
            assistant_id="test-assistant-id",
            tool_id="test-tool-id",
        )

    @pytest.mark.asyncio
    async def test_save_memory_success(self, save_tool):
        """Test successful memory save."""
        from tools.memory_tool import MemorySaveTool

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(MemorySaveTool, "get_client", return_value=mock_client):
            result = await save_tool._execute(
                text="User likes Python programming",
                memory_type="user_fact",
                importance=7,
            )

            assert result == "Воспоминание успешно сохранено."
            mock_client.post.assert_called_once_with(
                "/api/memory/",
                json={
                    "user_id": 123,
                    "text": "User likes Python programming",
                    "memory_type": "user_fact",
                    "importance": 7,
                    "assistant_id": "test-assistant-id",
                },
            )

    @pytest.mark.asyncio
    async def test_save_memory_no_user_id(self, mock_settings):
        """Test that save fails without user_id."""
        from tools.memory_tool import MemorySaveTool
        from utils.error_handler import ToolError

        tool = MemorySaveTool(
            name="save_memory",
            description="Save a memory",
            settings=mock_settings,
            user_id=None,
            assistant_id="test-assistant-id",
            tool_id="test-tool-id",
        )

        with pytest.raises(ToolError) as exc_info:
            await tool._execute(text="Test memory")

        assert exc_info.value.error_code == "USER_ID_REQUIRED"

    @pytest.mark.asyncio
    async def test_save_memory_invalid_user_id(self, mock_settings):
        """Test that save fails with invalid user_id format."""
        from tools.memory_tool import MemorySaveTool
        from utils.error_handler import ToolError

        tool = MemorySaveTool(
            name="save_memory",
            description="Save a memory",
            settings=mock_settings,
            user_id="not-an-integer",
            assistant_id="test-assistant-id",
            tool_id="test-tool-id",
        )

        with pytest.raises(ToolError) as exc_info:
            await tool._execute(text="Test memory")

        assert exc_info.value.error_code == "INVALID_USER_ID_FORMAT"

    @pytest.mark.asyncio
    async def test_save_memory_api_error(self, save_tool):
        """Test handling of API errors."""
        from tools.memory_tool import MemorySaveTool
        from utils.error_handler import ToolError

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

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(MemorySaveTool, "get_client", return_value=mock_client):
            with pytest.raises(ToolError) as exc_info:
                await save_tool._execute(text="Test memory")

            assert exc_info.value.error_code == "API_ERROR"

    @pytest.mark.asyncio
    async def test_save_memory_network_error(self, save_tool):
        """Test handling of network errors."""
        from tools.memory_tool import MemorySaveTool
        from utils.error_handler import ToolError

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.RequestError("Connection failed")
        )

        with patch.object(MemorySaveTool, "get_client", return_value=mock_client):
            with pytest.raises(ToolError) as exc_info:
                await save_tool._execute(text="Test memory")

            assert exc_info.value.error_code == "NETWORK_ERROR"


class TestMemorySearchTool:
    """Tests for MemorySearchTool."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with RAG service URL."""
        settings = MagicMock()
        settings.RAG_SERVICE_URL = "http://rag-service:8002"
        return settings

    @pytest.fixture
    def search_tool(self, mock_settings):
        """Create MemorySearchTool instance with mocked settings."""
        from tools.memory_tool import MemorySearchTool

        return MemorySearchTool(
            name="search_memory",
            description="Search memories",
            settings=mock_settings,
            user_id="123",
            assistant_id="test-assistant-id",
            tool_id="test-tool-id",
        )

    @pytest.mark.asyncio
    async def test_search_memories_success(self, search_tool):
        """Test successful memory search."""
        from tools.memory_tool import MemorySearchTool

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value=[
                {
                    "text": "User likes Python",
                    "memory_type": "user_fact",
                    "score": 0.95,
                },
                {
                    "text": "User prefers dark mode",
                    "memory_type": "preference",
                    "score": 0.87,
                },
            ]
        )
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(MemorySearchTool, "get_client", return_value=mock_client):
            result = await search_tool._execute(
                query="What does user like?",
                limit=5,
            )

            assert "Найденные воспоминания:" in result
            assert "User likes Python" in result
            assert "0.95" in result
            mock_client.post.assert_called_once_with(
                "/api/memory/search",
                json={
                    "query": "What does user like?",
                    "user_id": 123,
                    "limit": 5,
                    "threshold": 0.5,
                },
            )

    @pytest.mark.asyncio
    async def test_search_memories_empty_result(self, search_tool):
        """Test search when no memories found."""
        from tools.memory_tool import MemorySearchTool

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=[])
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(MemorySearchTool, "get_client", return_value=mock_client):
            result = await search_tool._execute(query="Unknown topic")

            assert result == "Релевантных воспоминаний не найдено."

    @pytest.mark.asyncio
    async def test_search_memories_no_user_id(self, mock_settings):
        """Test that search fails without user_id."""
        from tools.memory_tool import MemorySearchTool
        from utils.error_handler import ToolError

        tool = MemorySearchTool(
            name="search_memory",
            description="Search memories",
            settings=mock_settings,
            user_id=None,
            assistant_id="test-assistant-id",
            tool_id="test-tool-id",
        )

        with pytest.raises(ToolError) as exc_info:
            await tool._execute(query="Test query")

        assert exc_info.value.error_code == "USER_ID_REQUIRED"

    @pytest.mark.asyncio
    async def test_search_memories_api_error(self, search_tool):
        """Test handling of API errors."""
        from tools.memory_tool import MemorySearchTool
        from utils.error_handler import ToolError

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

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(MemorySearchTool, "get_client", return_value=mock_client):
            with pytest.raises(ToolError) as exc_info:
                await search_tool._execute(query="Test query")

            assert exc_info.value.error_code == "API_ERROR"

    @pytest.mark.asyncio
    async def test_search_memories_network_error(self, search_tool):
        """Test handling of network errors."""
        from tools.memory_tool import MemorySearchTool
        from utils.error_handler import ToolError

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.RequestError("Connection failed")
        )

        with patch.object(MemorySearchTool, "get_client", return_value=mock_client):
            with pytest.raises(ToolError) as exc_info:
                await search_tool._execute(query="Test query")

            assert exc_info.value.error_code == "NETWORK_ERROR"

    def test_get_client_no_settings(self, mock_settings):
        """Test that get_client fails without RAG_SERVICE_URL."""
        from tools.memory_tool import MemorySearchTool
        from utils.error_handler import ToolError

        mock_settings.RAG_SERVICE_URL = None
        tool = MemorySearchTool(
            name="search_memory",
            description="Search memories",
            settings=mock_settings,
            user_id="123",
            assistant_id="test-assistant-id",
            tool_id="test-tool-id",
        )

        with pytest.raises(ToolError) as exc_info:
            tool.get_client()

        assert exc_info.value.error_code == "CONFIGURATION_ERROR"
