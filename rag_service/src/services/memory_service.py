"""Memory service for interacting with rest_service Memory endpoints."""

from uuid import UUID

from openai import OpenAI
from shared_models import get_logger

from config.settings import settings
from services.rest_client import get_rest_client

logger = get_logger(__name__)


class MemoryService:
    """Service for Memory V2 operations via rest_service."""

    def __init__(self) -> None:
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.embedding_model = settings.EMBEDDING_MODEL
        self._rest_client = get_rest_client()

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
        embedding = await self.generate_embedding(query)

        results = await self._rest_client.search_memories(
            embedding=embedding,
            user_id=user_id,
            limit=limit,
            threshold=threshold,
        )
        logger.info(
            "Memory search completed",
            query_length=len(query),
            results_count=len(results),
        )
        return results

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
        embedding = await self.generate_embedding(text)

        memory = await self._rest_client.create_memory(
            user_id=user_id,
            text=text,
            memory_type=memory_type,
            embedding=embedding,
            assistant_id=assistant_id,
            importance=importance,
        )
        return memory
