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
├── manage.py                # Project management script
├── run_tests.sh            # Test execution script
├── run_formatters.sh       # Code formatting script
├── docker-compose.yml      # Main Docker configuration
├── pyproject.toml          # Poetry configuration
└── poetry.lock            # Fixed dependency versions
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
├── llm_context_*.md      # Service documentation
└── __init__.py           # Package initialization
```

## Services

The project is divided into several independent microservices:

- **assistant_service**  
  - Core engine for handling user messages and coordinating various LLM-based functionalities.
  - Manages context, threads, and asynchronous message processing via Redis.
  - Processes standard messages (`HumanMessage`, `ToolMessage`) and internal events (`reminder_triggered`) from the input Redis queue (`REDIS_QUEUE_TO_SECRETARY`).
  - Utilizes the `create_reminder` tool to interact with `rest_service` for creating reminders.
  - Handles triggered reminders by processing them as `ToolMessage`.
  - Supports multiple secretary instances with user-specific configurations.
  - Implements secretary selection and caching through `AssistantFactory`.
  - Sends responses to `telegram_bot_service` via the output Redis queue (`REDIS_QUEUE_TO_TELEGRAM`).
  
- **rest_service**  
  - Provides a REST API for managing user data, assistant configurations, and related models.
  - Handles CRUD operations for assistants, tools, **and reminders (`Reminder` model and `/api/reminders/` endpoints)**.
  - Stores reminder data (one-time and recurring) in PostgreSQL.
  - Manages user-secretary mapping and secretary configurations.
  - Uses PostgreSQL for data storage and Alembic for database migrations.
  
- **google_calendar_service**  
  - Integrates with Google Calendar for event management.
  - Implements OAuth 2.0 authorization, token management, and calendar event retrieval/creation.
  
- **cron_service**  
  - A scheduler service using APScheduler **focused on executing scheduled reminders**.
  - Periodically pulls **active reminder configurations** from `rest_service` (`GET /api/reminders/scheduled`).
  - Schedules reminders using APScheduler (`DateTrigger` / `CronTrigger`).
  - Sends **`reminder_triggered` events** via Redis (`REDIS_QUEUE_TO_SECRETARY`) when a reminder executes.
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

The project includes several management scripts:

- **manage.py** - Main management script for:
  - Database migrations
  - Service testing
  - Container management
  - Service lifecycle control

- **run_tests.sh** - Script for running tests in Docker containers
- **run_formatters.sh** - Script for code formatting and linting

Detailed information about each service is available in their respective `llm_context_*.md` files.

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
  - `OPENAI_API_KEY`: OpenAI API key
  - `OPEN_API_SECRETAR_ID`: OpenAI Assistant ID
  - `TELEGRAM_TOKEN`: Telegram Bot token
  - `GOOGLE_*`: Google Calendar API credentials

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
# Run all tests
./run_tests.sh

# Run tests for specific services
./run_tests.sh rest_service assistant_service

# Available services:
# - rest_service
# - cron_service
# - telegram_bot_service
# - assistant_service
# - google_calendar_service
# - rag_service
```

### Test Environment

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

### Management Scripts

The project provides several management scripts for development and deployment:

#### manage.py

Main management script with the following commands:

```bash
# Database Management
./manage.py migrate "Migration message"  # Create new migration
./manage.py upgrade                      # Apply pending migrations

# Service Management
./manage.py start [--service SERVICE]    # Start service(s)
./manage.py stop [--service SERVICE]     # Stop service(s)
./manage.py restart [--service SERVICE]  # Restart service(s)
./manage.py rebuild [--service SERVICE]  # Rebuild service(s)

# Testing
./manage.py test [--service SERVICE]     # Run tests

# Code Formatting
./manage.py black [--service SERVICE]    # Run black formatter
./manage.py isort [--service SERVICE]    # Run isort formatter
```

#### run_tests.sh

Test execution script:
```bash
# Run all tests
./run_tests.sh

# Run specific service tests
./run_tests.sh rest_service assistant_service
```

#### run_formatters.sh

Code formatting script:
- Runs black and isort on changed files
- Checks formatting before commit
- Provides instructions for fixing formatting issues

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

detailed information on each service in the "llm_context_**" files