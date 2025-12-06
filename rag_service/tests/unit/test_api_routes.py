import json
from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.models.rag_models import RagData, SearchQuery, SearchResult


# Добавляем JSON-сериализатор для UUID и datetime
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


# Переопределяем метод model_dump для тестов
def model_dump_with_uuid(obj):
    data = obj.model_dump()
    return json.loads(json.dumps(data, cls=CustomJSONEncoder))


client = TestClient(app)


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


@pytest.fixture
def sample_search_query():
    # Создаем вектор размерности 1536
    query_embedding = [0.1] * 1536
    return SearchQuery(
        query_embedding=query_embedding,
        data_type="test_data",
        user_id=123,
        assistant_id=uuid4(),
        top_k=5,
    )


@pytest.fixture
def sample_search_results():
    return [
        SearchResult(
            id=uuid4(),
            text="Результат 1",
            distance=0.1,
            metadata={
                "data_type": "test_data",
                "user_id": "123",
                "assistant_id": str(uuid4()),
            },
        ),
        SearchResult(
            id=uuid4(),
            text="Результат 2",
            distance=0.2,
            metadata={
                "data_type": "test_data",
                "user_id": "123",
                "assistant_id": str(uuid4()),
            },
        ),
    ]


def test_add_data_endpoint(sample_rag_data):
    with patch("src.services.vector_db_service.QdrantClient") as mock_client:
        # Настраиваем мок для get_collections
        mock_collections = MagicMock()
        mock_collections.collections = []
        mock_client.return_value.get_collections.return_value = mock_collections

        response = client.post(
            "/api/data/add", json=model_dump_with_uuid(sample_rag_data)
        )

        assert response.status_code == 200
        assert UUID(response.json()["id"]) == sample_rag_data.id
        assert response.json()["text"] == sample_rag_data.text
        assert response.json()["data_type"] == sample_rag_data.data_type


def test_search_data_endpoint(sample_search_query, sample_search_results):
    with patch("src.services.vector_db_service.QdrantClient") as mock_client:
        # Настраиваем мок для get_collections
        mock_collections = MagicMock()
        mock_collections.collections = []
        mock_client.return_value.get_collections.return_value = mock_collections

        # Настраиваем мок для search
        mock_client.return_value.search.return_value = [
            MagicMock(
                id=str(result.id),
                score=result.distance,
                payload={"text": result.text, **result.metadata},
            )
            for result in sample_search_results
        ]

        response = client.post(
            "/api/data/search", json=model_dump_with_uuid(sample_search_query)
        )

        assert response.status_code == 200
        assert len(response.json()) == len(sample_search_results)
        for i, result in enumerate(response.json()):
            assert UUID(result["id"]) == sample_search_results[i].id
            assert result["text"] == sample_search_results[i].text
            assert result["distance"] == sample_search_results[i].distance


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
