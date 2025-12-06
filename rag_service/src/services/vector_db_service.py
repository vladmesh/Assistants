from uuid import UUID

import structlog
from qdrant_client import QdrantClient
from qdrant_client.http import models

from config.settings import settings
from models.rag_models import RagData, SearchResult

logger = structlog.get_logger()


class VectorDBService:
    """Сервис для взаимодействия с векторной базой данных Qdrant."""

    def __init__(self):
        self.client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        self._ensure_collection()

    def _ensure_collection(self):
        """Создает коллекцию, если она не существует."""
        try:
            collections = self.client.get_collections().collections
            collection_names = [collection.name for collection in collections]

            if settings.QDRANT_COLLECTION_NAME not in collection_names:
                self.client.create_collection(
                    collection_name=settings.QDRANT_COLLECTION_NAME,
                    vectors_config=models.VectorParams(
                        size=1536,  # Размерность векторов для OpenAI embeddings
                        distance=models.Distance.COSINE,
                    ),
                )
                logger.info(f"Created collection: {settings.QDRANT_COLLECTION_NAME}")
        except Exception as e:
            logger.error(f"Error ensuring collection exists: {e}")
            raise

    async def add_data(self, rag_data: RagData) -> None:
        """Добавляет данные в векторную базу данных."""
        try:
            metadata = rag_data.model_dump(exclude={"embedding", "text", "id"})
            metadata["user_id"] = (
                str(metadata["user_id"]) if metadata["user_id"] else None
            )
            metadata["assistant_id"] = (
                str(metadata["assistant_id"]) if metadata["assistant_id"] else None
            )

            self.client.upsert(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                points=[
                    models.PointStruct(
                        id=str(rag_data.id),
                        vector=rag_data.embedding,
                        payload={"text": rag_data.text, **metadata},
                    )
                ],
            )
            logger.info(f"Data added to vector DB with id: {rag_data.id}")
        except Exception as e:
            logger.error(f"Error adding data to vector DB: {e}")
            raise

    async def search_data(
        self,
        query_embedding: list[float],
        data_type: str,
        user_id: int | None,
        assistant_id: UUID | None,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Ищет данные в векторной базе данных."""
        try:
            search_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="data_type", match=models.MatchValue(value=data_type)
                    )
                ]
            )

            if user_id:
                search_filter.must.append(
                    models.FieldCondition(
                        key="user_id", match=models.MatchValue(value=str(user_id))
                    )
                )

            if assistant_id:
                search_filter.must.append(
                    models.FieldCondition(
                        key="assistant_id",
                        match=models.MatchValue(value=str(assistant_id)),
                    )
                )

            search_results = self.client.search(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=top_k,
            )

            results = []
            for hit in search_results:
                results.append(
                    SearchResult(
                        id=UUID(hit.id),
                        text=hit.payload["text"],
                        distance=hit.score,
                        metadata={k: v for k, v in hit.payload.items() if k != "text"},
                    )
                )

            logger.info(f"Search completed, found {len(results)} results")
            return results
        except Exception as e:
            logger.error(f"Error searching vector DB: {e}")
            raise

    def get_client(self):
        """Возвращает клиент Qdrant для прямого доступа при необходимости."""
        return self.client
