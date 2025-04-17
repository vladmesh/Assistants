# План реализации RAG сервиса

## 1. Настройка проекта для `rag_service`

*   **Создание структуры директорий:**
    ```bash
    mkdir rag_service
    cd rag_service
    mkdir src tests alembic src/api src/config src/models src/services src/scripts src/alembic
    touch src/__init__.py tests/__init__.py src/api/__init__.py src/config/__init__.py src/models/__init__.py src/services/__init__.py src/scripts/__init__.py src/alembic/__init__.py
    touch src/main.py src/config/settings.py src/api/routes.py src/services/vector_db_service.py src/models/rag_models.py
    touch Dockerfile Dockerfile.test docker-compose.test.yml pyproject.toml llm_context_rag.md
    ```

*   **`pyproject.toml` - Определение зависимостей:**

    ```toml
    [tool.poetry]
    name = "rag-service"
    version = "0.1.0"
    description = "RAG Service for Smart Assistant"
    authors = ["Your Name <your.email@example.com>"]
    packages = [{ include = "src" }]

    [tool.poetry.dependencies]
    python = "^3.11"
    fastapi = "^0.109.2"
    uvicorn = "^0.27.1"
    pydantic = "^2.6.1"
    pydantic-settings = "^2.1.0"
    python-dotenv = "^1.0.1"
    structlog = "^24.1.0"
    qdrant-client = "^1.7.1" # Клиент для Qdrant
    httpx = "^0.26.0"
    shared-models = {path = "../shared_models"} # Добавить общие модели


    [tool.poetry.group.dev.dependencies]
    flake8 = "^6.1.0"
    flake8-pyproject = "^1.2.3"
    mypy = "^1.6.1"
    pylint = "^3.0.2"
    autoflake = "^2.3.1"

    [tool.poetry.group.test.dependencies]
    pytest = "^7.4.3"
    pytest-asyncio = "^0.21.1"
    pytest-cov = "^4.1.0"
    pytest-mock = "^3.12.0"

    [tool.pytest.ini_options]
    testpaths = ["tests"]
    python_files = ["test_*.py"]
    addopts = "-v --cov=src --cov-report=term-missing"
    asyncio_mode = "auto"

    [tool.mypy]
    python_version = "3.11"
    warn_return_any = true
    warn_unused_configs = true
    disallow_untyped_defs = true
    disallow_incomplete_defs = true
    check_untyped_defs = true
    disallow_untyped_decorators = true
    no_implicit_optional = true
    warn_redundant_casts = true
    warn_unused_ignores = true
    warn_no_return = true
    warn_unreachable = true
    strict_optional = true
    mypy_path = "src"
    ```

*   **`Dockerfile` и `Dockerfile.test`**: Использовать шаблоны из `docker_templates.md`, заменив `service_name` на `rag_service`.
*   **`docker-compose.test.yml`**: Использовать шаблон из `docker_templates.md`, настроив имя сервиса и зависимости (вероятно Redis для кэширования и потенциально тестовую БД, если вы решите сохранять векторные данные для тестов).
*   **`llm_context_rag.md`**: Создать базовый файл документации на основе `service_template.md` и заполнить обзор, структуру директорий и т.д.

## 2. Реализация конфигурации (`rag_service/src/config/settings.py`)

Добавим параметры для подключения к Qdrant контейнеру.

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Rag Service Settings."""

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "DEBUG"
    API_PORT: int = 8002 # Выбрать уникальный порт
    
    # Qdrant settings
    QDRANT_HOST: str = "qdrant"  # Имя сервиса в docker-compose
    QDRANT_PORT: int = 6333      # REST API порт
    QDRANT_COLLECTION: str = "rag_data"  # Имя коллекции в Qdrant

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
```

## 3. Реализация сервиса векторной базы данных (`rag_service/src/services/vector_db_service.py`)

Заменим ChromaDB на Qdrant. Необходимо использовать клиент `qdrant-client` и настроить подключение к контейнеру.

```python
from typing import List, Optional, UUID
import structlog
from src.config.settings import settings
from src.models.rag_models import RagData, SearchResult
from qdrant_client import QdrantClient, models


logger = structlog.get_logger()

class VectorDBService:
    """Сервис для взаимодействия с векторной базой данных."""

    def __init__(self):
        self.client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        self.collection_name = settings.QDRANT_COLLECTION
        
        # Создаем коллекцию, если она не существует
        try:
            self.client.get_collection(self.collection_name)
        except Exception:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=1536,  # Размерность векторов (зависит от модели эмбеддингов)
                    distance=models.Distance.COSINE
                )
            )
            logger.info(f"Created collection: {self.collection_name}")

    async def add_data(self, rag_data: RagData) -> None:
        """Добавляет данные в векторную базу данных."""
        try:
            self.client.upsert(
                collection_name=self.collection_name,
                points=models.Batch(
                    ids=[rag_data.id],
                    payloads=[rag_data.model_dump()], # Сохраняем всю модель как payload
                    vectors=[rag_data.embedding]
                )
            )
            logger.info(f"Data added to vector DB with id: {rag_data.id}")
        except Exception as e:
            logger.error(f"Error adding data to vector DB: {e}")
            raise

    async def search_data(self, query_embedding: List[float], data_type: str, user_id: Optional[int], assistant_id: Optional[UUID], top_k: int = 5) -> List[SearchResult]:
        """Ищет данные в векторной базе данных."""
        try:
            # Создаем фильтр для поиска
            search_filter = models.Filter(
                must=[
                    models.FieldCondition(key="data_type", match=models.MatchValue(value=data_type))
                ]
            )
            
            # Добавляем условия для user_id и assistant_id, если они указаны
            if user_id:
                search_filter.must.append(
                    models.FieldCondition(key="user_id", match=models.MatchValue(value=str(user_id)))
                )
            if assistant_id:
                search_filter.must.append(
                    models.FieldCondition(key="assistant_id", match=models.MatchValue(value=str(assistant_id)))
                )
            
            # Выполняем поиск
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=top_k
            )
            
            # Преобразуем результаты
            results = []
            for hit in search_results:
                results.append(SearchResult(
                    id=hit.id,
                    text=hit.payload['text'],
                    distance=hit.score,
                    metadata=hit.payload
                ))
            
            logger.info(f"Search completed, found {len(results)} results")
            return results
        except Exception as e:
            logger.error(f"Error searching vector DB: {e}")
            raise

    def get_client(self): # Для прямого доступа при необходимости
        return self.client
```

## 4. Определение моделей данных (`rag_service/src/models/rag_models.py`)

```python
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

class RagData(BaseModel):
    """Модель для данных, хранящихся в RAG сервисе."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    text: str = Field(..., description="Текстовое содержимое")
    embedding: List[float] = Field(..., description="Векторное представление текста")
    data_type: str = Field(..., description="Тип данных (например, 'shared_rule', 'user_history', 'assistant_note')")
    user_id: Optional[int] = Field(None, description="ID пользователя, если данные специфичны для пользователя")
    assistant_id: Optional[UUID] = Field(None, description="ID ассистента, если данные специфичны для ассистента")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class SearchQuery(BaseModel):
    """Модель для поисковых запросов к RAG сервису."""
    query_embedding: List[float] = Field(..., description="Векторное представление запроса")
    data_type: str = Field(..., description="Тип данных для поиска")
    user_id: Optional[int] = Field(None, description="Фильтр по ID пользователя")
    assistant_id: Optional[UUID] = Field(None, description="Фильтр по ID ассистента")
    top_k: int = Field(default=5, description="Количество результатов для возврата")

class SearchResult(BaseModel):
    """Модель для результатов поиска из RAG сервиса."""
    id: UUID
    text: str
    distance: float
    metadata: Dict[str, Any]
```

## 5. Реализация API эндпоинтов (`rag_service/src/api/routes.py`)

```python
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from src.services.vector_db_service import VectorDBService
from src.models.rag_models import RagData, SearchQuery, SearchResult

router = APIRouter()

async def get_vector_db_service() -> VectorDBService:
    """Зависимость для получения VectorDBService."""
    return VectorDBService()

@router.post("/data/add", response_model=RagData)
async def add_data_endpoint(rag_data: RagData, vector_db_service: VectorDBService = Depends(get_vector_db_service)):
    """Эндпоинт для добавления данных в векторную базу данных."""
    try:
        await vector_db_service.add_data(rag_data)
        return rag_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/data/search", response_model=List[SearchResult])
async def search_data_endpoint(search_query: SearchQuery, vector_db_service: VectorDBService = Depends(get_vector_db_service)):
    """Эндпоинт для поиска данных в векторной базе данных."""
    try:
        results = await vector_db_service.search_data(
            query_embedding=search_query.query_embedding,
            data_type=search_query.data_type,
            user_id=search_query.user_id,
            assistant_id=search_query.assistant_id,
            top_k=search_query.top_k
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## 6. Основное приложение (`rag_service/src/main.py`)

```python
from fastapi import FastAPI
from src.api.routes import router
from src.config.settings import settings
import structlog

logger = structlog.get_logger()

app = FastAPI(
    title="RAG Service",
    description="Service for Retrieval-Augmented Generation",
    version="0.1.0",
)

app.include_router(router, prefix="/api", tags=["RAG Data"])

@app.on_event("startup")
async def startup_event():
    logger.info("Starting RAG service")

@app.get("/health")
async def health_check():
    """Эндпоинт проверки работоспособности."""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.API_PORT)
```

## 7. Обновление `docker-compose.yml`

Добавить `rag_service` и `qdrant` в основной файл `docker-compose.yml`, обеспечив их подключение к той же сети и передачу необходимых переменных окружения. Выбрать порт (например, 8002 для `rag_service` и 6333:6334 для `qdrant`) и добавить проверку работоспособности.

## 8. Интеграция с `assistant_service` (Концептуально)

*   **Добавить зависимость**: В `assistant_service/pyproject.toml` добавить `httpx` и объявить зависимость от `rag_service`.
*   **Создать `RAGTool`**: В `assistant_service/src/tools/rag_tool.py` создать класс `RAGTool`.
    *   `__init__`: Инициализировать `httpx.AsyncClient` для связи с `rag_service`.
    *   `execute(query: str, data_type: str, user_id: int, assistant_id: UUID)`:
        *   Получить эмбеддинг запроса `query` (используя ту же модель эмбеддингов, что и для индексации данных, вероятно из OpenAI API или локальной модели эмбеддингов).
        *   Вызвать эндпоинт `/api/data/search` сервиса `rag_service` с эмбеддингом, `data_type`, `user_id` и `assistant_id`.
        *   Обработать и вернуть результаты поиска.
*   **Зарегистрировать `RAGTool`**: В `assistant_service` зарегистрировать `RAGTool` как тип инструмента.
*   **Использовать `RAGTool` в логике ассистента**: Изменить логику ассистента (промпты, вызов функций и т.д.), чтобы использовать `RAGTool`, когда требуется генерация с извлечением информации.

## Следующие шаги:

1.  **Реализовать код**: Создать файлы и вставить фрагменты кода в них.
2.  **Реализовать тесты**: Написать модульные и интеграционные тесты для `rag_service`.
3.  **Докеризировать и запустить**: Собрать и запустить `rag_service` с помощью Docker Compose.
4.  **Интегрировать с `assistant_service`**: Реализовать `RAGTool` и интегрировать его в рабочий процесс ассистента.
5.  **Протестировать интеграцию**: Тщательно протестировать интеграцию между `assistant_service` и `rag_service`.
6.  **Документировать**: Обновить `llm_context_rag.md` и `llm_context.md` с подробностями о новом сервисе.

Не забудьте установить зависимости с помощью `poetry install` в директории `rag_service` после создания файла `pyproject.toml`. Этот подробный план должен дать вам прочную отправную точку для реализации вашего RAG микросервиса. 