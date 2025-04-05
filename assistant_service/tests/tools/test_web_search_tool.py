"""Tests for web search tool"""

from unittest.mock import MagicMock, patch

import pytest
from config.settings import Settings
from tools.web_search_tool import WebSearchTool
from utils.error_handler import ToolExecutionError


@pytest.fixture
def settings():
    """Create settings fixture"""
    settings = Settings()
    settings.TAVILY_API_KEY = "test_api_key"
    return settings


@pytest.fixture
def web_search_tool(settings):
    """Create web search tool fixture"""
    return WebSearchTool(settings=settings)


@pytest.mark.asyncio
async def test_web_search_tool_initialization(web_search_tool):
    """Test web search tool initialization"""
    assert web_search_tool.name == "web_search"
    assert "Search the internet" in web_search_tool.description
    assert web_search_tool.client is None


@pytest.mark.asyncio
async def test_web_search_tool_execute_no_api_key():
    """Test web search tool execution without API key"""
    settings = Settings()
    settings.TAVILY_API_KEY = None
    tool = WebSearchTool(settings=settings)

    with pytest.raises(ToolExecutionError) as excinfo:
        await tool._execute("test query")

    assert "Tavily API key not configured" in str(excinfo.value)


@pytest.mark.asyncio
async def test_web_search_tool_execute_with_mock(web_search_tool):
    """Test web search tool execution with mock"""
    # Mock TavilyClient
    mock_client = MagicMock()
    mock_client.search.return_value = {
        "results": [
            {
                "title": "Test Title",
                "url": "https://example.com",
                "content": "Test content",
            }
        ]
    }

    # Patch TavilyClient
    with patch("tools.web_search_tool.TavilyClient", return_value=mock_client):
        result = await web_search_tool._execute("test query")

        # Check result format
        assert "Search Results:" in result
        assert "Test Title" in result
        assert "https://example.com" in result
        assert "Test content" in result

        # Check client was called correctly
        mock_client.search.assert_called_once_with(
            query="test query", search_depth="basic", max_results=5
        )


@pytest.mark.asyncio
async def test_web_search_tool_execute_with_invalid_depth(web_search_tool):
    """Test web search tool execution with invalid search depth"""
    # Mock TavilyClient
    mock_client = MagicMock()
    mock_client.search.return_value = {
        "results": [
            {
                "title": "Test Title",
                "url": "https://example.com",
                "content": "Test content",
            }
        ]
    }

    # Patch TavilyClient
    with patch("tools.web_search_tool.TavilyClient", return_value=mock_client):
        result = await web_search_tool._execute("test query", search_depth="invalid")

        # Check client was called with default search depth
        mock_client.search.assert_called_once_with(
            query="test query", search_depth="basic", max_results=5
        )


@pytest.mark.asyncio
async def test_web_search_tool_execute_with_invalid_max_results(web_search_tool):
    """Test web search tool execution with invalid max_results"""
    # Mock TavilyClient
    mock_client = MagicMock()
    mock_client.search.return_value = {
        "results": [
            {
                "title": "Test Title",
                "url": "https://example.com",
                "content": "Test content",
            }
        ]
    }

    # Patch TavilyClient
    with patch("tools.web_search_tool.TavilyClient", return_value=mock_client):
        # Test with max_results < 1
        result = await web_search_tool._execute("test query", max_results=0)
        mock_client.search.assert_called_with(
            query="test query", search_depth="basic", max_results=1
        )

        # Test with max_results > 10
        result = await web_search_tool._execute("test query", max_results=20)
        mock_client.search.assert_called_with(
            query="test query", search_depth="basic", max_results=10
        )


@pytest.mark.asyncio
async def test_web_search_tool_execute_with_no_results(web_search_tool):
    """Test web search tool execution with no results"""
    # Mock TavilyClient
    mock_client = MagicMock()
    mock_client.search.return_value = {"results": []}

    # Patch TavilyClient
    with patch("tools.web_search_tool.TavilyClient", return_value=mock_client):
        result = await web_search_tool._execute("test query")
        assert "No search results found" in result


@pytest.mark.asyncio
async def test_web_search_tool_execute_with_exception(web_search_tool):
    """Test web search tool execution with exception"""
    # Mock TavilyClient
    mock_client = MagicMock()
    mock_client.search.side_effect = Exception("Test error")

    # Patch TavilyClient
    with patch("tools.web_search_tool.TavilyClient", return_value=mock_client):
        with pytest.raises(ToolExecutionError) as excinfo:
            await web_search_tool._execute("test query")

        assert "Web search failed" in str(excinfo.value)
