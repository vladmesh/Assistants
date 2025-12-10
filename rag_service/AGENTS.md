# RAG Service

## Обзор

RAG сервис сейчас работает поверх `rest_service` (pgvector) через Memory API и не содержит собственной векторной БД.

## Структура директорий

```
rag_service/
├── src/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── memory_routes.py
│   │   └── routes.py          # health
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── memory_service.py  # работает через rest_service
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

### Memory API (через rest_service)

- `POST /api/memory/search` — генерирует embedding в RAG, ищет в `rest_service` (pgvector).
- `POST /api/memory/` — генерирует embedding и создаёт память через `rest_service`.
- `GET /api/health` и корневой `/health` — проверки.

## Интеграция с Assistant Service

Ассистент использует REST эндпоинты `rest_service` для хранения/поиска памяти; RAG сервис лишь генерирует embedding и проксирует вызовы.

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
