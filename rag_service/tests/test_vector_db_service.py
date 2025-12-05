from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from src.models.rag_models import RagData, SearchResult
from src.services.vector_db_service import VectorDBService


@pytest.fixture
def mock_qdrant_client():
    with patch("src.services.vector_db_service.QdrantClient") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def vector_db_service(mock_qdrant_client):
    service = VectorDBService()
    return service


@pytest.fixture
def sample_rag_data():
    # Создаем вектор размерности 1536
    embedding = [0.1] * 1536
    return RagData(
        id=uuid4(),
        text="Тестовый текст",
        embedding=embedding,
        data_type="test_data",
        user_id=123,
        assistant_id=uuid4(),
        timestamp=datetime.now(),
    )


@pytest.mark.asyncio
async def test_add_data(vector_db_service, mock_qdrant_client, sample_rag_data):
    # Настраиваем мок для get_collections
    mock_collections = MagicMock()
    mock_collections.collections = []
    mock_qdrant_client.get_collections.return_value = mock_collections

    await vector_db_service.add_data(sample_rag_data)

    # Проверяем, что create_collection был вызван с правильными параметрами
    mock_qdrant_client.create_collection.assert_called_once()
    # Проверяем, что upsert был вызван
    mock_qdrant_client.upsert.assert_called_once()


@pytest.mark.asyncio
async def test_search_data(vector_db_service, mock_qdrant_client):
    # Настраиваем мок для get_collections
    mock_collections = MagicMock()
    mock_collections.collections = []
    mock_qdrant_client.get_collections.return_value = mock_collections

    # Подготавливаем данные для теста
    query_embedding = [0.1] * 1536
    data_type = "test_data"
    user_id = 123
    assistant_id = uuid4()
    top_k = 2

    # Создаем UUID для тестовых результатов
    result_id1 = uuid4()
    result_id2 = uuid4()

    # Мокаем результат запроса
    mock_qdrant_client.search.return_value = [
        MagicMock(
            id=str(result_id1),
            score=0.1,
            payload={
                "text": "doc1",
                "data_type": "test_data",
                "user_id": "123",
                "assistant_id": str(assistant_id),
            },
            vector=[0.1] * 1536,
        ),
        MagicMock(
            id=str(result_id2),
            score=0.2,
            payload={
                "text": "doc2",
                "data_type": "test_data",
                "user_id": "123",
                "assistant_id": str(assistant_id),
            },
            vector=[0.1] * 1536,
        ),
    ]

    results = await vector_db_service.search_data(
        query_embedding=query_embedding,
        data_type=data_type,
        user_id=user_id,
        assistant_id=assistant_id,
        top_k=top_k,
    )

    # Проверяем, что search был вызван с правильными параметрами
    mock_qdrant_client.search.assert_called_once()
    assert len(results) == 2
    assert all(isinstance(result, SearchResult) for result in results)
    assert results[0].id == result_id1
    assert results[1].id == result_id2
