"""Web search tool using Tavily API"""

from typing import Optional, Type

from config.logger import get_logger
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

    # Restore the Type annotation
    args_schema: Type[WebSearchInput] = WebSearchInput
    # Remove custom __init__ to inherit from BaseTool

    # Class attribute for the client, initialized lazily
    _client: Optional[TavilyClient] = None

    def _get_tavily_client(self) -> TavilyClient:
        """Lazy initialization of the Tavily client."""
        if self._client is None:
            if not self.settings or not self.settings.TAVILY_API_KEY:
                logger.error("Tavily API key not configured for WebSearchTool.")
                raise ToolExecutionError("Tavily API key not configured", self.name)
            try:
                self._client = TavilyClient(api_key=self.settings.TAVILY_API_KEY)
            except Exception as e:
                logger.error(f"Failed to initialize TavilyClient: {e}", exc_info=True)
                raise ToolExecutionError(
                    f"Failed to initialize Tavily client: {str(e)}", self.name
                )
        return self._client

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
            # Get client lazily
            client = self._get_tavily_client()

            # Validate search depth
            if search_depth not in ["basic", "deep"]:
                logger.warning(f"Invalid search_depth '{search_depth}', using 'basic'.")
                search_depth = "basic"

            # Validate max_results
            max_results = max(1, min(10, max_results))  # Clamp between 1 and 10

            logger.info(
                "Executing web search",
                query=query,
                search_depth=search_depth,
                max_results=max_results,
            )

            # Perform search
            # Note: TavilyClient.search is synchronous, run in executor?
            # For now, calling directly.
            search_result = client.search(
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
                logger.info("No search results found for query.", query=query)
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

            logger.info(f"Web search successful, returning {len(results)} results.")
            return formatted_results.strip()

        except ToolExecutionError as e:  # Re-raise config errors
            raise e
        except Exception as e:
            logger.error("Web search failed", query=query, error=str(e), exc_info=True)
            raise ToolExecutionError(f"Web search failed: {str(e)}", self.name) from e
