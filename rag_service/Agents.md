# RAG Service

## Обзор

RAG (Retrieval-Augmented Generation) сервис предоставляет функциональность для хранения и поиска векторных эмбеддингов текстовых данных. Сервис использует векторную базу данных ChromaDB для эффективного хранения и поиска по эмбеддингам.

## Структура директорий

```
rag_service/
├── src/
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── rag_models.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── vector_db_service.py
│   ├── scripts/
│   │   └── __init__.py
│   ├── __init__.py
│   └── main.py
├── tests/
│   └── __init__.py
├── Dockerfile
├── Dockerfile.test
├── docker-compose.test.yml
├── pyproject.toml
└── llm_context_rag.md
```

## API Эндпоинты

### Добавление данных

```
POST /api/data/add
```

Добавляет новые данные в векторную базу данных.

**Тело запроса:**
```json
{
  "text": "Текстовое содержимое",
  "embedding": [0.1, 0.2, 0.3, ...],
  "data_type": "shared_rule",
  "user_id": 123,
  "assistant_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Ответ:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "text": "Текстовое содержимое",
  "embedding": [0.1, 0.2, 0.3, ...],
  "data_type": "shared_rule",
  "user_id": 123,
  "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2023-01-01T00:00:00Z"
}
```

### Поиск данных

```
POST /api/data/search
```

Ищет данные в векторной базе данных по эмбеддингу запроса.

**Тело запроса:**
```json
{
  "query_embedding": [0.1, 0.2, 0.3, ...],
  "data_type": "shared_rule",
  "user_id": 123,
  "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
  "top_k": 5
}
```

**Ответ:**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "text": "Текстовое содержимое",
    "distance": 0.123,
    "metadata": {
      "data_type": "shared_rule",
      "user_id": 123,
      "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
      "timestamp": "2023-01-01T00:00:00Z"
    }
  }
]
```

### Проверка работоспособности

```
GET /health
```

Проверяет работоспособность сервиса.

**Ответ:**
```json
{
  "status": "healthy"
}
```

## Интеграция с Assistant Service

RAG сервис интегрируется с Assistant Service через инструмент `RAGTool`, который позволяет ассистентам использовать функциональность RAG для генерации ответов с учетом контекста из векторной базы данных.

## Запуск и тестирование

### Запуск сервиса

```bash
cd rag_service
poetry install
poetry run python -m src.main
```

### Запуск тестов

```bash
cd rag_service
poetry install
poetry run pytest
```

### Запуск в Docker

```bash
cd rag_service
docker build -t rag-service .
docker run -p 8002:8002 rag-service
```

### Запуск тестов в Docker

```bash
cd rag_service
docker compose -f docker-compose.test.yml up --build
```
