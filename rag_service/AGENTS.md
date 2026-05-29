# RAG Service

## Overview

The RAG service currently runs on top of `rest_service` (pgvector) via the Memory API and does not contain its own vector database.

## Directory Structure

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
│   │   └── memory_service.py  # works through rest_service
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

## API Endpoints

### Memory API (through rest_service)

- `POST /api/memory/search` — generates an embedding in RAG, searches in `rest_service` (pgvector).
- `POST /api/memory/` — generates an embedding and creates a memory via `rest_service`.
- `GET /api/health` and root `/health` — health checks.

## Integration with the Assistant Service

The assistant uses the `rest_service` REST endpoints to store/search memory; the RAG service only generates the embedding and proxies the calls.

## Running and Testing

### Running the Service

```bash
cd rag_service
poetry install
poetry run python -m src.main
```

### Running Tests

```bash
cd rag_service
poetry install
poetry run pytest
```

### Running in Docker

```bash
cd rag_service
docker build -t rag-service .
docker run -p 8002:8002 rag-service
```

### Running Tests in Docker

```bash
cd rag_service
docker compose -f docker-compose.test.yml up --build
```
