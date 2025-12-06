"""Memory service for interacting with rest_service Memory endpoints."""

from uuid import UUID

import httpx
import structlog
from openai import OpenAI

from src.config.settings import settings

logger = structlog.get_logger()


class MemoryService:
    """Service for Memory V2 operations via rest_service."""

    def __init__(self) -> None:
        self.base_url = settings.REST_SERVICE_URL
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.embedding_model = settings.EMBEDDING_MODEL

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for text using OpenAI."""
        try:
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text,
            )
            embedding = response.data[0].embedding
            logger.info("Generated embedding", text_length=len(text))
            return embedding
        except Exception as e:
            logger.error("Error generating embedding", error=str(e))
            raise

    async def search_memories(
        self,
        query: str,
        user_id: int,
        limit: int = 10,
        threshold: float = 0.7,
    ) -> list[dict]:
        """Search for relevant memories using text query.

        1. Generate embedding for query
        2. Call rest_service /memories/search
        3. Return results
        """
        # Generate embedding
        embedding = await self.generate_embedding(query)

        # Call rest_service
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/memories/search",
                    json={
                        "embedding": embedding,
                        "user_id": user_id,
                        "limit": limit,
                        "threshold": threshold,
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                results = response.json()
                logger.info(
                    "Memory search completed",
                    query_length=len(query),
                    results_count=len(results),
                )
                return results
            except httpx.HTTPStatusError as e:
                logger.error(
                    "REST service error",
                    status_code=e.response.status_code,
                    detail=e.response.text,
                )
                raise
            except Exception as e:
                logger.error("Error searching memories", error=str(e))
                raise

    async def create_memory(
        self,
        user_id: int,
        text: str,
        memory_type: str,
        assistant_id: UUID | None = None,
        importance: int = 1,
    ) -> dict:
        """Create a new memory with embedding.

        1. Generate embedding for text
        2. Call rest_service POST /memories
        3. Return created memory
        """
        # Generate embedding
        embedding = await self.generate_embedding(text)

        # Call rest_service
        async with httpx.AsyncClient() as client:
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

                response = await client.post(
                    f"{self.base_url}/api/memories/",
                    json=payload,
                    timeout=30.0,
                )
                response.raise_for_status()
                memory = response.json()
                logger.info(
                    "Memory created",
                    memory_id=memory.get("id"),
                    memory_type=memory_type,
                )
                return memory
            except httpx.HTTPStatusError as e:
                logger.error(
                    "REST service error",
                    status_code=e.response.status_code,
                    detail=e.response.text,
                )
                raise
            except Exception as e:
                logger.error("Error creating memory", error=str(e))
                raise
