"""
REST client for rag_service using BaseServiceClient.

Provides unified HTTP communication with rest_service.
"""

from uuid import UUID

from shared_models import BaseServiceClient, ClientConfig, get_logger

from config.settings import settings

logger = get_logger(__name__)


class RagRestClient(BaseServiceClient):
    """REST client for rag_service to communicate with rest_service."""

    def __init__(self, base_url: str | None = None):
        config = ClientConfig(
            timeout=30.0,
            connect_timeout=5.0,
            max_retries=3,
            retry_min_wait=1.0,
            retry_max_wait=10.0,
            circuit_breaker_fail_max=5,
            circuit_breaker_reset_timeout=60.0,
        )
        super().__init__(
            base_url=base_url or settings.REST_SERVICE_URL,
            service_name="rag_service",
            target_service="rest_service",
            config=config,
        )

    async def search_memories(
        self,
        embedding: list[float],
        user_id: int,
        limit: int = 10,
        threshold: float = 0.7,
    ) -> list[dict]:
        """Search memories by embedding vector."""
        try:
            result = await self.request(
                "POST",
                "/api/memories/search",
                json={
                    "embedding": embedding,
                    "user_id": user_id,
                    "limit": limit,
                    "threshold": threshold,
                },
            )
            memories = result if isinstance(result, list) else []
            logger.info("Memory search completed", results_count=len(memories))
            return memories
        except Exception as e:
            logger.error("Failed to search memories", error=str(e))
            raise

    async def create_memory(
        self,
        user_id: int,
        text: str,
        memory_type: str,
        embedding: list[float],
        assistant_id: UUID | str | None = None,
        importance: int = 1,
    ) -> dict:
        """Create a new memory with embedding."""
        try:
            payload = {
                "user_id": user_id,
                "text": text,
                "memory_type": memory_type,
                "embedding": embedding,
                "importance": importance,
            }
            if assistant_id:
                payload["assistant_id"] = str(assistant_id)

            result = await self.request("POST", "/api/memories/", json=payload)
            if result:
                logger.info(
                    "Memory created",
                    memory_id=result.get("id"),
                    memory_type=memory_type,
                )
            return result if isinstance(result, dict) else {}
        except Exception as e:
            logger.error("Failed to create memory", error=str(e))
            raise


# Singleton instance
_client: RagRestClient | None = None


def get_rest_client() -> RagRestClient:
    """Get or create REST client singleton."""
    global _client
    if _client is None:
        _client = RagRestClient()
    return _client


async def close_rest_client() -> None:
    """Close the REST client."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None
