# High-Level Overview

## Project Structure

The project is organized as a monorepo with the following structure:

```
smart-assistant/
├── assistant_service/          # Core assistant service
├── rest_service/              # REST API service
├── google_calendar_service/   # Google Calendar integration
├── cron_service/             # Task scheduler service
├── telegram_bot_service/     # Telegram bot interface
├── rag_service/             # RAG service
├── scripts/                  # Utility scripts
├── Makefile                # Lint/format/test entrypoint (dockerized ruff/pytest)
├── .pre-commit-config.yaml # Ruff hooks for commits
├── docker-compose.yml      # Main Docker configuration
└── docker-compose-prod.yml # Production compose (GHCR images)
```

Each service follows a consistent structure:
```
service_name/
├── src/                    # Source code
├── tests/                  # Test suite
├── Dockerfile             # Main Dockerfile
├── Dockerfile.test        # Test environment Dockerfile
├── docker-compose.test.yml # Test environment configuration
├── pyproject.toml     # Service dependencies
├── Agents.md             # Service documentation
└── __init__.py           # Package initialization
```

## Services

The project is divided into several independent microservices:

- **assistant_service**  
  - Core engine for handling user messages and coordinating various LLM-based functionalities.
  - Manages context, threads, and asynchronous message processing via Redis.
  - Processes standard messages (`HumanMessage`, `ToolMessage`) and internal events (`reminder_triggered`) from the input Redis queue (`REDIS_QUEUE_TO_SECRETARY`).
  - Utilizes the reminder creation tool (`ReminderTool`) to interact with `rest_service` for creating reminders.
  - Handles triggered reminders by processing them as `HumanMessage`.
  - Supports multiple secretary instances with user-specific configurations.
  - Implements secretary selection and caching through `AssistantFactory`, which also manages tool creation via an internal `ToolFactory`.
  - Sends responses to `telegram_bot_service` via the output Redis queue (`REDIS_QUEUE_TO_TELEGRAM`).
  
- **rest_service**  
  - Provides a REST API for managing core project models and configurations.
  - Handles CRUD operations for Users, Assistants, Tools, Reminders, User-Secretary mappings, and potentially Calendar tokens.
  - Stores data (assistants, tools, reminders, users, etc.) in PostgreSQL.
  - Manages user-secretary mapping and assistant/tool configurations.
  - Uses PostgreSQL for data storage and Alembic for database migrations.
  
- **google_calendar_service**  
  - Integrates with Google Calendar for event management.
  - Implements OAuth 2.0 authorization, token management, and calendar event retrieval/creation.
  
- **cron_service**  
  - A scheduler service using APScheduler for managing scheduled tasks, primarily reminders.
  - Periodically pulls active reminder configurations from `rest_service` (`GET /api/reminders/scheduled`) to update its internal job list (`update_jobs_from_rest` task).
  - Schedules individual reminder jobs using APScheduler (`DateTrigger` / `CronTrigger`).
  - Sends `reminder_triggered` events via Redis (`REDIS_QUEUE_TO_SECRETARY`) when a reminder job executes.
  - Updates the status of completed one-time reminders in `rest_service` (`PATCH /api/reminders/{id}`).
  
- **telegram_bot_service**  
  - A Telegram Bot interface for end-user interaction.
  - Receives user messages, identifies users via REST API, and sends formatted responses.
  
- **rag_service**  
  - Retrieval-Augmented Generation service for context-aware responses.
  - Integrates with Qdrant vector database for storing and retrieving text embeddings.
  - Provides API endpoints for adding and searching vector data.
  - Supports filtering by data type, user, and assistant.
  - Enhances assistant responses with relevant context from the vector database.

## Project Management

Центральная точка входа — корневой `Makefile` (dockerized):
- `make format [SERVICE=rest_service]` — `ruff format` + `ruff check --fix`.
- `make lint [SERVICE=rest_service]` — `ruff check`.
- `make test [SERVICE=rest_service]` — docker-compose.test.yml (или python:3.11 для shared_models).
- Миграции rest_service: добавить новые цели (старый manage.py удалён).

Pre-commit: `.pre-commit-config.yaml` (ruff --fix + ruff-format).

Подробности по сервисам — в их `AGENTS.md`.

## Deployment

### Docker & Docker Compose

The project uses Docker Compose for container orchestration. Each service runs in its own container with the following configuration:

- **Base Services:**
  - `redis`: Redis server for message queues and caching
  - `db`: PostgreSQL database for persistent storage
  - `rest_service`: REST API service (port 8000)
  - `google_calendar_service`: Calendar integration (port 8001)
  - `assistant_service`: Core assistant service
  - `telegram_bot_service`: Telegram bot interface
  - `cron_service`: Task scheduler service
  - `rag_service`: RAG service (port 8002)
  - `qdrant`: Vector database for embeddings storage

- **Container Management:**
  ```bash
  # Build and start all containers
  docker compose up --build -d

  # Check container status
  docker compose ps

  # View logs for a specific service
  docker compose logs -f assistant_service

  # Restart a specific service
  docker compose restart assistant_service
  ```

- **Health Checks:**
  - Each service implements health checks
  - Services wait for dependencies to be healthy before starting
  - Automatic retries and timeouts are configured

### Environment Configuration

The project uses environment variables for configuration:

- **Core Services:**
  - `POSTGRES_*`: Database configuration
  - `REDIS_*`: Redis connection settings
  - `ASYNC_DATABASE_URL`: Async database connection string
  - `QDRANT_*`: Qdrant vector database configuration

- **API Keys & Secrets:**
  - `OPENAI_API_KEY`: OpenAI API key (used by LangGraphAssistant).
  - `TELEGRAM_TOKEN`: Telegram Bot token.
  - `TAVILY_API_KEY`: Tavily API key for web search tool (optional).
  - `GOOGLE_*`: Google Calendar API credentials.

- **Service Communication:**
  - `REDIS_QUEUE_TO_TELEGRAM`: Queue for messages from `assistant_service` to `telegram_bot_service`.
  - `REDIS_QUEUE_TO_SECRETARY`: Queue for messages from `telegram_bot_service` and **`reminder_triggered` events from `cron_service`** to `assistant_service`.
  - `REST_SERVICE_URL`: REST API endpoint used by `assistant_service`, `cron_service`, etc.

### Development Setup

For development:
- Source code is mounted as volumes for live updates
- Each service has its own test environment (`docker-compose.test.yml`)
- Health checks ensure proper service initialization
- Network isolation using Docker networks

### Testing Environment

- Separate Docker Compose configuration for tests
- Isolated test databases and Redis instances
- Automated test execution in containers
- Health checks for test services

## Testing

### Test Types and Structure

The project implements a comprehensive testing strategy with the following components:

- **Unit Tests:**
  - Validate individual components and business logic
  - Use mocks for external dependencies
  - Focus on isolated functionality testing

- **Integration Tests:**
  - Verify inter-service communication
  - Test API endpoints and database operations
  - Validate asynchronous operations

- **End-to-End Tests:**
  - Test complete user workflows
  - Run in isolated Docker environments
  - Validate service interactions

### Test Execution

Tests are executed using Docker containers for isolation and consistency:

```bash
# Build base test image (required once, or after shared_models changes)
make build-test-base

# Run unit tests (fast, no DB/Redis required)
make test-unit SERVICE=assistant_service
make test-unit SERVICE=cron_service
make test-unit SERVICE=shared_models
make test-unit  # all services

# Run integration tests (legacy, uses docker-compose.test.yml per service)
make test SERVICE=rest_service
make test SERVICE=assistant_service
make test  # all services

# Available services: rest_service, cron_service, telegram_bot_service,
# assistant_service, google_calendar_service, rag_service, admin_service, shared_models
```

### Test Environment

**Unit Tests (new approach):**

Uses a single base image (`assistants-test-base`) with pytest and shared_models pre-installed. Service-specific dependencies are installed at runtime via poetry.

- **Docker Configuration:**
  - `Dockerfile.test-base` - Base test image with pytest + shared_models
  - `docker-compose.unit-test.yml` - Unit test runner (mounts service code)
  - No DB/Redis required for unit tests

**Integration Tests (per service):**

Each service has its own test environment:

- **Docker Configuration:**
  - `Dockerfile.test` - Test-specific Dockerfile
  - `docker-compose.test.yml` - Test environment configuration
  - Isolated databases and Redis instances

- **Environment Variables:**
  - `TESTING=1` - Test mode flag
  - `PYTHONPATH=/src` - Source code path
  - `ASYNC_DATABASE_URL` - Test database connection
  - Service-specific test configurations

### Test Management

- **Test Results:**
  - Color-coded output for better visibility
  - Detailed error reporting
  - Service-specific test status

- **Test Isolation:**
  - Each service runs in its own container
  - Clean environment for each test run
  - Automatic cleanup after tests

- **Continuous Integration:**
  - Automated test execution
  - Service-specific test suites
  - Integration with CI/CD pipeline

### Best Practices

- **Test Organization:**
  - Clear separation of test types
  - Consistent naming conventions
  - Proper test isolation

- **Test Data:**
  - Use of fixtures and factories
  - Clean test data management
  - Proper cleanup after tests

- **Test Coverage:**
  - Coverage reports for each service
  - Integration with coverage tools
  - Regular coverage monitoring

## Scripts & Tools

### Management

- Корневой `Makefile` (lint/format/test).
- `.pre-commit-config.yaml` (ruff hooks).
- manage.py/run_tests.sh/run_formatters.sh — удалены, неактуальны.

### Development Tools

#### Code Formatters
- **Black**: Python code formatter
- **isort**: Import statement sorter
- **flake8**: Code style checker
- **mypy**: Static type checker

#### Testing Tools
- **pytest**: Test framework
- **pytest-asyncio**: Async test support
- **pytest-cov**: Coverage reporting
- **pytest-mock**: Mocking utilities

#### Database Tools
- **Alembic**: Database migrations
- **SQLAlchemy**: ORM and database toolkit
- **psycopg2**: PostgreSQL adapter
- **Qdrant**: Vector database for embeddings

#### Container Management
- **Docker**: Containerization
- **Docker Compose**: Container orchestration
- **Health Checks**: Service monitoring

### Best Practices

- **Code Formatting:**
  - Run formatters before committing
  - Use consistent formatting rules
  - Check formatting in CI/CD

- **Testing:**
  - Write tests for new features
  - Maintain test coverage
  - Run tests in containers

- **Database:**
  - Use migrations for schema changes
  - Test migrations before deployment
  - Maintain migration history

- **Container Management:**
  - Use health checks
  - Monitor container status
  - Follow container best practices

---

This high-level summary encapsulates the primary components, deployment strategy, testing approach, and management scripts/tools of the Smart Assistant project.

# General Recommendations and Future Plans

## Best Practices & Internal Guidelines

- **Code Quality:**
  - Use consistent naming conventions (snake_case for services, kebab-case for containers)
  - Follow standardized service structure
  - Maintain high test coverage
  - Use type hints and static type checking

- **Development Workflow:**
  - Run formatters before committing
  - Use pre-commit hooks for code quality
  - Test changes in Docker containers
  - Document all significant changes

- **Security:**
  - Validate configuration at startup
  - Use environment-specific configuration
  - Implement proper secret management
  - Regular dependency updates

- **Container Management:**
  - Use health checks for all services
  - Monitor container status
  - Follow Docker best practices
  - Maintain clean container images

### Current Status

✅ Completed:
- Standardized naming conventions
- Service structure standardization
- Linter implementation
- Basic dependency management
- Initial documentation updates
- RAG service implementation

🔄 In Progress:
- Dependency updates
- Configuration system improvements
- Service-specific updates
- Testing infrastructure

⏳ Planned:
- Enhanced monitoring and logging
- CI/CD pipeline improvements
- Advanced testing capabilities
- Documentation updates

### Future Enhancements

#### Configuration & Security
- Implement centralized configuration management
- Add configuration validation
- Improve secret management
- Environment-specific configurations

#### Testing & Quality
- Increase test coverage (>80%)
- Add integration tests
- Implement performance testing
- Enhance CI/CD pipeline

#### Monitoring & Observability
- Centralized logging with structlog
- Prometheus metrics integration
- Grafana dashboards
- Request tracing

#### Documentation
- Update service documentation
- Add development guidelines
- Create API documentation
- Maintain change logs

### Roadmap

1. **Short-term (1-2 months):**
   - Complete dependency updates
   - Implement configuration system
   - Update service documentation
   - Add basic monitoring

2. **Medium-term (3-6 months):**
   - Enhance testing infrastructure
   - Improve CI/CD pipeline
   - Add advanced monitoring
   - Update all services

3. **Long-term (6+ months):**
   - Implement advanced features
   - Optimize performance
   - Scale infrastructure
   - Enhance security

### Success Criteria

- All services follow standardized structure
- High test coverage (>80%)
- Secure configuration management
- Efficient monitoring and logging
- Comprehensive documentation
- Successful CI/CD pipeline
- Regular dependency updates
- Clean and maintainable code

Detailed information on each service in their respective `Agents.md` files.

---

## Architecture Decision Records

### ADR-001: LangGraph + LangChain as Primary Framework (2025-12)

**Context:** The project initially experimented with multiple approaches for LLM orchestration:
- Direct OpenAI Assistants API
- Raw LangChain chains
- LangGraph state machines

**Decision:** Standardize on **LangGraph** with **LangChain** integrations.

**Rationale:**
- LangGraph provides flexible state machine for complex workflows (summarization, tool calls, sub-assistants)
- LangChain offers mature tool abstractions and LLM provider integrations
- Database-based persistence (via REST API) gives more control than LangGraph checkpointers
- ReAct agent pattern (`create_react_agent`) handles tool calling elegantly

**Consequences:**
- Removed legacy `OPENAI_API` assistant type and related code
- Removed `openai_assistant_id` field and `UserAssistantThread` table
- Single `AssistantType.LLM` for all assistants using LangGraph
- All context/state management done through custom graph nodes and REST API