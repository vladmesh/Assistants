"""Web search tool using Tavily API"""

from typing import Optional

from config.logger import get_logger
from config.settings import Settings
from pydantic import BaseModel, Field
from tavily import TavilyClient
from tools.base import BaseTool
from utils.error_handler import ToolExecutionError

logger = get_logger(__name__)


class WebSearchInput(BaseModel):
    """Schema for web search input"""

    query: str = Field(description="Search query to find information on the internet")
    search_depth: str = Field(
        default="basic", description="Search depth: must be either 'basic' or 'deep'"
    )
    max_results: int = Field(
        default=5, description="Maximum number of search results to return (1-10)"
    )


class WebSearchTool(BaseTool):
    """Tool for searching the internet using Tavily API"""

    settings: Settings = Field(default=None)
    client: Optional[TavilyClient] = Field(default=None)

    def __init__(self, settings: Settings, user_id: Optional[str] = None):
        """Initialize the web search tool

        Args:
            settings: Application settings
            user_id: Optional user identifier for tool context
        """
        super().__init__(
            name="web_search",
            description="Search the internet for information on a specific topic",
            args_schema=WebSearchInput,
            user_id=user_id,
        )
        self.settings = settings
        self.client = None

    async def _execute(
        self, query: str, search_depth: str = "basic", max_results: int = 5
    ) -> str:
        """Execute web search using Tavily API

        Args:
            query: Search query
            search_depth: Search depth ('basic' or 'deep')
            max_results: Maximum number of results to return

        Returns:
            Search results as formatted string

        Raises:
            ToolExecutionError: If search fails
        """
        try:
            # Initialize client if not already done
            if self.client is None:
                if not self.settings or not self.settings.TAVILY_API_KEY:
                    raise ToolExecutionError("Tavily API key not configured", self.name)
                self.client = TavilyClient(api_key=self.settings.TAVILY_API_KEY)

            # Validate search depth
            if search_depth not in ["basic", "deep"]:
                search_depth = "basic"

            # Validate max_results
            if max_results < 1:
                max_results = 1
            elif max_results > 10:
                max_results = 10

            logger.info(
                "Executing web search",
                query=query,
                search_depth=search_depth,
                max_results=max_results,
            )

            # Perform search
            search_result = self.client.search(
                query=query,
                search_depth=search_depth,
                max_results=max_results,
            )

            # Format results
            if (
                not search_result
                or "results" not in search_result
                or not search_result["results"]
            ):
                return "No search results found."

            results = search_result["results"]
            formatted_results = "Search Results:\n\n"

            for i, result in enumerate(results, 1):
                title = result.get("title", "No title")
                url = result.get("url", "No URL")
                content = result.get("content", "No content")

                formatted_results += f"{i}. {title}\n"
                formatted_results += f"   URL: {url}\n"
                formatted_results += f"   {content}\n\n"

            return formatted_results

        except Exception as e:
            logger.error("Web search failed", error=str(e))
            raise ToolExecutionError(f"Web search failed: {str(e)}", self.name)
