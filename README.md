# Smart Assistant

A comprehensive intelligent assistant system built on LangChain and LangGraph, designed to manage various aspects of daily life through natural language processing.

## Architecture

### Services
- **assistant_service** - Core assistant service
  - Uses LangChain 1.x + LangGraph 1.x
  - Manages context and conversation history via REST API
  - Coordinates tool operations (calendar, reminders, RAG, web-search)
  - Reads from `REDIS_QUEUE_TO_SECRETARY`, writes to `REDIS_QUEUE_TO_TELEGRAM`
- **rest_service** - REST API service
  - FastAPI + SQLModel with PostgreSQL (pgvector)
  - Manages user data, assistants, tools, reminders, facts
  - Provides tool configurations to assistant service
  - CRUD operations for all business entities
- **google_calendar_service** - Google Calendar integration
  - OAuth 2.0 authorization and token management
  - Event management operations
  - Integrates with REST service and Redis queues
- **cron_service** - Reminder scheduler service
  - APScheduler for job execution
  - Pulls active reminders from REST service
  - Sends `reminder_triggered` events to `REDIS_QUEUE_TO_SECRETARY`
  - Exposes Prometheus metrics on port 8080
- **telegram_bot_service** - Telegram bot interface
  - Receives and sends Telegram messages
  - Resolves users via REST API
  - Bridges events to/from Redis queues
- **admin_service** - Administrative interface (Streamlit)
  - User and assistant management
  - Tool configuration
  - Monitoring dashboards (logs, metrics, queues, jobs)
  - System settings
- **rag_service** - Retrieval-Augmented Generation service
  - REST API for adding/searching embeddings
  - Uses OpenAI embeddings
  - In-memory storage (no external vector DB)
  - Integration with assistant service

### Technology Stack
- Python 3.11
- LangChain 1.x + LangGraph 1.x (assistant orchestration)
- FastAPI (REST services), Streamlit (admin panel)
- PostgreSQL with pgvector extension
- Redis (message queues)
- Docker & Docker Compose
- OpenAI API (chat + embeddings)
- Tavily (optional web search)
- Poetry for dependency management (per-service)
- Ruff for code formatting and linting
- Pytest for testing
- Structlog for structured logging

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd smart-assistant
```

2. Create a `.env` file with required environment variables (see `.env.example` for reference):
```bash
# Database
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name
ASYNC_DATABASE_URL=postgresql+asyncpg://user:password@db:5432/dbname

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_QUEUE_TO_TELEGRAM=queue:to:telegram
REDIS_QUEUE_TO_SECRETARY=queue:to:secretary

# External APIs
OPENAI_API_KEY=your_openai_api_key
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_BOT_USERNAME=your_bot_username

# Google Calendar OAuth
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=your_google_redirect_uri

# Service URLs
REST_SERVICE_URL=http://rest_service:8000
```

3. Start services using Docker Compose:
```bash
docker compose up --build -d
```

4. (Optional) Start monitoring stack:
```bash
cd monitoring
docker compose -f docker-compose.monitoring.yml --env-file ../.env up -d
```

## Development

### Development Environment
All development is done in Docker containers to ensure consistency across environments. The project uses Docker Compose for service orchestration and development.

### Code Quality
- Форматирование и линт: Ruff (format + check) в контейнерах через Makefile
- Pre-commit hooks: `pre-commit install` (на commit: `make format`, на push: `make lint && make test-unit`)
- Запуск для конкретного сервиса:
```bash
make format SERVICE=rest_service      # ruff format + ruff check --fix
make lint SERVICE=rest_service        # ruff check
make format-check SERVICE=rest_service # ruff format --check (CI)
```
- Все сервисы сразу:
```bash
make format
make lint
make format-check
```

### Testing
- **Unit tests**: Fast tests without DB/Redis dependencies
  ```bash
  make build-test-base                # Build base test image (run once)
  make test-unit [SERVICE=...]        # Run unit tests for service(s)
  make test-unit assistant_service    # Example: test specific service
  ```
- **Integration tests**: Tests with DB/Redis (rest_service, assistant_service, telegram_bot_service)
  ```bash
  make test-integration [SERVICE=...]  # Run integration tests
  make test-integration all            # Test all services
  ```
- **All tests**:
  ```bash
  make test-all                        # Run unit + integration tests
  ```

### CI/CD
- **`ci.yml`**: Format check, lint, unit tests (all services), integration tests (rest/assistant/telegram) on PR and push to main
- **`docker-publish.yml`**: Build and push images to GHCR on push to main (tags: `sha` and `latest`)
- **`deploy-prod.yml`**: Manual dispatch or `v*` tag; SSH to production and `docker compose pull && up -d` with `IMAGE_TAG`/`REGISTRY` variables

### Миграции (rest_service)
```bash
# создать миграцию (MESSAGE="..."):
make migrate MESSAGE="add new table"
# применить все:
make upgrade
# история:
make history
```

### Project Structure
```
.
├── assistant_service/        # LangGraph assistant service
├── rest_service/            # REST API + PostgreSQL (pgvector)
├── google_calendar_service/ # Google Calendar OAuth + events
├── cron_service/            # APScheduler reminder triggers
├── telegram_bot_service/    # Telegram bot interface
├── admin_service/           # Streamlit admin panel
├── rag_service/             # RAG API (OpenAI embeddings)
├── shared_models/           # Shared Pydantic schemas and enums
├── monitoring/              # Monitoring stack (Grafana, Prometheus, Loki)
├── scripts/                 # Utility scripts
├── docs/                    # Architecture and design documentation
├── Makefile                 # Development commands (lint, format, tests)
├── docker-compose.yml       # Main development stack
├── docker-compose.unit-test.yml      # Unit test configuration
├── docker-compose.integration.yml    # Integration test configuration
└── .pre-commit-config.yaml  # Git hooks configuration
```

## Service Communication

### Request Flow
1. User sends message via Telegram bot
2. `telegram_bot_service` resolves user via REST API and pushes `HumanMessage` to `REDIS_QUEUE_TO_SECRETARY`
3. `assistant_service` reads from queue, processes with LangGraph
4. Assistant uses tools (calendar, reminders, RAG, web-search) via REST API
5. Messages and facts stored in PostgreSQL via REST API
6. Response pushed to `REDIS_QUEUE_TO_TELEGRAM`
7. `telegram_bot_service` sends response to user

### Message Queues (Redis)
- `REDIS_QUEUE_TO_SECRETARY`: Input queue for assistant service
  - `HumanMessage` from Telegram bot
  - `reminder_triggered` events from cron service
- `REDIS_QUEUE_TO_TELEGRAM`: Output queue for Telegram bot
  - Assistant responses to users

### Database (PostgreSQL with pgvector)
- User data and authentication
- Assistant configurations
- Tool configurations
- Reminders and job executions
- User facts and memory
- Message history
- Vector embeddings (via pgvector)

## Monitoring

The project includes a comprehensive monitoring stack based on Grafana, Prometheus, and Loki.

### Monitoring Stack
- **Grafana**: Dashboards for logs, metrics, queues, and job executions
- **Prometheus**: Metrics collection from services and exporters
- **Loki**: Centralized log aggregation
- **Promtail**: Log collection from Docker containers

### Quick Start
```bash
# 1. Start main services
docker compose up -d

# 2. Start monitoring stack
cd monitoring
docker compose -f docker-compose.monitoring.yml --env-file ../.env up -d
```

### Access
- **Grafana**: http://localhost:3000 (admin/admin or `GRAFANA_ADMIN_PW`)
- **Prometheus**: http://localhost:9090
- **Loki**: http://localhost:3100

### Features
- **Pre-configured dashboards**: Overview, Logs, Service Communication
- **Metrics**: HTTP requests, errors, queue sizes, job executions
- **Alerting**: Telegram notifications for critical issues (service down, high error rates, etc.)
- **Log aggregation**: Structured logs from all services with filtering by service/level

See [monitoring/README.md](monitoring/README.md) for detailed setup and configuration.

### Logging
- Structured logging with structlog (JSON format)
- Correlation IDs for request tracing
- Log levels: DEBUG, INFO, WARNING, ERROR
- Docker logs accessible via `docker compose logs -f <service>`

### Health Checks
- All services expose `/health` endpoints
- Docker Compose healthchecks with automatic retries
- Service dependency verification

## Documentation

Detailed implementation and architecture documentation is available in `docs/`:
- [service_template.md](docs/service_template.md) - Service structure template
- [naming_conventions.md](docs/naming_conventions.md) - Coding standards
- [docker_templates.md](docs/docker_templates.md) - Docker configuration patterns
- [poetry_requirements.md](docs/poetry_requirements.md) - Dependency management guidelines
- [monitoring_implementation_plan.md](docs/monitoring_implementation_plan.md) - Monitoring architecture
- Additional design docs: memory, RAG, refactoring plans, testing strategies

For agent-specific context, see [AGENTS.md](AGENTS.md). 