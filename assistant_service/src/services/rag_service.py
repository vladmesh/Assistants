# assistant_service/src/services/rag_service.py
"""Client for communicating with RAG service for Memory V2 operations."""

import time
from uuid import UUID

import httpx
from shared_models import get_logger

from config.settings import Settings

logger = get_logger(__name__)


class RagServiceClient:
    """HTTP client for RAG service Memory V2 endpoints."""

    def __init__(self, settings: Settings):
        """Initialize the RAG service client.

        Args:
            settings: Application settings containing RAG service URL.
        """
        self.settings = settings
        self._client: httpx.AsyncClient | None = None

    @property
    def base_url(self) -> str:
        """Get RAG service base URL."""
        return self.settings.RAG_SERVICE_URL

    def get_client(self) -> httpx.AsyncClient:
        """Lazily initialize and return the httpx client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def search_memories(
        self,
        query: str,
        user_id: int,
        limit: int = 10,
        threshold: float = 0.7,
    ) -> list[dict]:
        """Search for relevant memories using semantic search.

        The RAG service generates embeddings for the query and calls
        rest_service for vector search.

        Args:
            query: Text query to search for.
            user_id: User ID to filter memories.
            limit: Maximum number of results to return.
            threshold: Minimum similarity threshold (0.0 to 1.0).

        Returns:
            List of memory dictionaries with similarity scores.
        """
        start_time = time.perf_counter()
        log_extra = {
            "user_id": user_id,
            "query_length": len(query),
            "limit": limit,
            "threshold": threshold,
        }

        try:
            client = self.get_client()
            response = await client.post(
                "/api/memory/search",
                json={
                    "query": query,
                    "user_id": user_id,
                    "limit": limit,
                    "threshold": threshold,
                },
            )
            response.raise_for_status()
            results = response.json()

            duration_ms = round((time.perf_counter() - start_time) * 1000)
            logger.info(
                "Memory search completed",
                duration_ms=duration_ms,
                results_count=len(results),
                **log_extra,
            )
            return results

        except httpx.HTTPStatusError as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000)
            logger.error(
                "RAG service error during memory search",
                duration_ms=duration_ms,
                status_code=e.response.status_code,
                detail=e.response.text,
                **log_extra,
            )
            raise

        except httpx.RequestError as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000)
            logger.error(
                "Network error during memory search",
                duration_ms=duration_ms,
                error=str(e),
                **log_extra,
            )
            raise

    async def create_memory(
        self,
        user_id: int,
        text: str,
        memory_type: str,
        assistant_id: UUID | None = None,
        importance: int = 1,
    ) -> dict:
        """Create a new memory with auto-generated embedding.

        The RAG service generates embeddings and calls rest_service to store.

        Args:
            user_id: User ID for the memory.
            text: Memory text content.
            memory_type: Type of memory (user_fact, conversation_insight, etc).
            assistant_id: Optional assistant ID (None = shared across all).
            importance: Importance level (1-10).

        Returns:
            Created memory dictionary.
        """
        start_time = time.perf_counter()
        log_extra = {
            "user_id": user_id,
            "memory_type": memory_type,
            "importance": importance,
            "text_length": len(text),
        }

        try:
            client = self.get_client()
            payload = {
                "user_id": user_id,
                "text": text,
                "memory_type": memory_type,
                "importance": importance,
            }
            if assistant_id:
                payload["assistant_id"] = str(assistant_id)

            response = await client.post(
                "/api/memory/",
                json=payload,
            )
            response.raise_for_status()
            memory = response.json()

            duration_ms = round((time.perf_counter() - start_time) * 1000)
            logger.info(
                "Memory created",
                duration_ms=duration_ms,
                memory_id=memory.get("id"),
                **log_extra,
            )
            return memory

        except httpx.HTTPStatusError as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000)
            logger.error(
                "RAG service error during memory creation",
                duration_ms=duration_ms,
                status_code=e.response.status_code,
                detail=e.response.text,
                **log_extra,
            )
            raise

        except httpx.RequestError as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000)
            logger.error(
                "Network error during memory creation",
                duration_ms=duration_ms,
                error=str(e),
                **log_extra,
            )
            raise
