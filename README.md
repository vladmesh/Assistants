# Smart Assistant

A comprehensive intelligent assistant system built on OpenAI Assistants API, designed to manage various aspects of daily life through natural language processing.

## Architecture

### Services
- **assistant_service** - Core assistant service
  - Uses OpenAI Assistants API
  - Manages context and conversation history
  - Coordinates tool operations
  - Supports multiple secretary instances
  - Handles user-secretary mapping
- **rest_service** - REST API service
  - Manages user data and configurations
  - Handles CRUD operations for assistants and tools
  - Manages user-secretary mapping
  - Uses PostgreSQL for data storage
- **google_calendar_service** - Google Calendar integration
  - Event management
  - OAuth 2.0 authorization
  - Token management
- **cron_service** - Task scheduler service
  - Job scheduling and execution
  - Notification handling
  - Task management
- **telegram_bot_service** - Telegram bot interface
  - User interaction
  - Message processing
  - Response formatting
- **admin_service** - Administrative interface
  - System management
  - Configuration control
  - Monitoring capabilities
- **rag_service** - Retrieval-Augmented Generation service
  - Storage and retrieval of text embeddings (in-memory)
  - Context-aware search functionality
  - Integration with assistant service

### Technology Stack
- Python 3.11+
- FastAPI
- PostgreSQL
- Redis
- Docker & Docker Compose
- OpenAI Assistants API
- Telegram Bot API
- Google Calendar API
- Poetry for dependency management
- Black & isort for code formatting
- Pytest for testing
- MyPy for type checking

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd smart-assistant
```

2. Create a `.env` file with required environment variables:
```bash
OPENAI_API_KEY=your_openai_api_key
TELEGRAM_TOKEN=your_telegram_bot_token
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name
ASYNC_DATABASE_URL=postgresql+asyncpg://user:password@db:5432/dbname
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=your_google_redirect_uri
```

3. Start services using Docker Compose:
```bash
docker compose up -d
```

## Development

### Development Environment
All development is done in Docker containers to ensure consistency across environments. The project uses Docker Compose for service orchestration and development.

### Code Quality
- Форматирование и линт: ruff (format + check) в контейнерах через Makefile.
- Перед коммитом: `pre-commit install` (ruff --fix и ruff-format).
- Запуск для конкретного сервиса (пример rest_service):
```bash
make format SERVICE=rest_service    # ruff format (правит код через bind mount)
make lint SERVICE=rest_service      # ruff check
make test SERVICE=rest_service      # docker compose -f rest_service/docker-compose.test.yml run test
```
- Все сервисы сразу:
```bash
make format
make lint
make test
```

### Testing
### CI/CD
- `ci.yml` — ruff format --check, ruff check, pytest для всех сервисов на PR и push в main.
- `docker-publish.yml` — сборка и пуш образов в GHCR на push в main, теги `sha` и `latest`.
- `deploy-prod.yml` — ручной запуск или по тегу `v*`: проверка наличия секретов, ssh на прод, `docker compose pull && up -d` с переменными `IMAGE_TAG`/`REGISTRY`.

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
├── assistant_service/     # Core assistant service
├── rest_service/         # REST API service
├── google_calendar_service/ # Calendar integration
├── cron_service/        # Task scheduler
├── telegram_bot_service/ # Telegram bot
├── admin_service/       # Admin interface
├── rag_service/         # RAG service
├── shared_models/       # Shared Pydantic schemas, Enums, and queue models
├── scripts/            # Utility scripts
├── manage.py          # Project management
├── run_tests.sh       # Test execution
├── run_formatters.sh  # Code formatting
├── docker-compose.yml # Docker configuration
├── pyproject.toml    # Poetry configuration
└── poetry.lock      # Fixed dependencies
```

## Service Communication

### Request Flow
1. User sends message via Telegram bot
2. Message processed by assistant service
3. Assistant determines required tools
4. Tools interact with respective services via REST API
5. Results returned to user via Telegram

### Message Queues
- Redis used for:
  - Conversation history
  - Tool result caching
  - Inter-service message queues
  - Health checks

### Database
- PostgreSQL used for:
  - User data
  - Assistant configurations
  - Interaction history
  - Task scheduling

## Monitoring

### Logging
- Structured logging with structlog
- Docker logs access
- Centralized log collection

### Health Checks
- Service health monitoring
- Dependency health verification
- Automatic retry mechanisms

## Documentation

Detailed implementation and architecture documentation is available in:
- [llm_context.md](llm_context.md) - High-level overview
- [service_template.md](service_template.md) - Service structure
- [naming_conventions.md](naming_conventions.md) - Coding standards
- [docker_templates.md](docker_templates.md) - Docker configuration
- [poetry_requirements.md](poetry_requirements.md) - Dependency management 