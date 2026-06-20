# RAG Service

A service for Retrieval-Augmented Generation (RAG): it generates OpenAI embeddings for text and stores/searches them in PostgreSQL (pgvector, HNSW + cosine) via the REST service.

## Features

- Store vector embeddings of text data
- Search embeddings by cosine similarity (PostgreSQL + pgvector, HNSW index)
- Support for various data types (shared rules, user history, assistant notes)
- Filtering by data type, user, and assistant
- REST API for adding and searching data

## Requirements

- Python 3.11+
- Poetry for dependency management
- Docker and Docker Compose (optional)

## Installation

### Local Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd rag_service
   ```

2. Install dependencies with Poetry:
   ```bash
   poetry install
   ```

3. Create a `.env` file based on the example:
   ```bash
   cp .env.example .env
   ```

4. Start the service:
   ```bash
   poetry run python -m src.main
   ```

### Installation with Docker

1. Build the image:
   ```bash
   docker build -t rag-service .
   ```

2. Run the container:
   ```bash
   docker run -p 8002:8002 rag-service
   ```

## Usage

### API Endpoints

#### Adding Data

```
POST /api/data/add
```

Adds new data to the vector database.

**Request body:**
```json
{
  "text": "Text content",
  "embedding": [0.1, 0.2, 0.3, ...],
  "data_type": "shared_rule",
  "user_id": 123,
  "assistant_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

#### Searching Data

```
POST /api/data/search
```

Searches the vector database by query embedding.

**Request body:**
```json
{
  "query_embedding": [0.1, 0.2, 0.3, ...],
  "data_type": "shared_rule",
  "user_id": 123,
  "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
  "top_k": 5
}
```

#### Health Check

```
GET /health
```

Checks the health of the service.

### Integration with the Assistant Service

The RAG service integrates with the Assistant Service via the `RAGTool` tool, which lets assistants use RAG functionality to generate responses that take context from the vector database into account.

## Testing

### Local Testing

```bash
poetry run pytest
```

### Testing with Docker

```bash
docker compose -f docker-compose.test.yml up --build
```

## License

MIT
