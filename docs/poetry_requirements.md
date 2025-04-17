# Poetry Requirements and Architecture

## 1. Overview

This document describes the requirements and architecture for using Poetry in our microservices project. The goal is to standardize dependency management and improve build efficiency across all services.

## 2. Project Structure

```
smart-assistant/
├── pyproject.toml           # Root project configuration
├── shared_models/          # Shared Pydantic models
│   └── pyproject.toml      # Shared models configuration
├── assistant_service/
│   └── pyproject.toml      # Assistant service configuration
├── rest_service/
│   └── pyproject.toml      # REST service configuration
├── google_calendar_service/
│   └── pyproject.toml      # Google Calendar service configuration
├── cron_service/
│   └── pyproject.toml      # Cron service configuration
└── telegram_bot_service/
    └── pyproject.toml      # Telegram bot service configuration
```

## 3. Requirements

### 3.1 Root Project Configuration
- Base Python version and dependencies
- Common development tools (black, isort, flake8, etc.)
- Shared linting and formatting rules
- Common test dependencies

### 3.2 Service-Specific Configuration
Each service should have its own `pyproject.toml` that:
- Inherits from the root configuration
- Defines service-specific dependencies
- Sets up service-specific linting rules
- Configures service-specific test dependencies

### 3.3 Shared Models
- Separate package for shared Pydantic models
- Versioned independently
- Used by all services for data validation
- Published as a separate package

### 3.4 Docker Integration
- Multi-stage builds using Poetry
- Separate test and production dependencies
- Minimal final image size
- Poetry.lock files for deterministic builds

## 4. Implementation Guidelines

### 4.1 Root pyproject.toml
```toml
[tool.poetry]
name = "smart-assistant"
version = "0.1.0"
description = "Smart Assistant Project"
authors = ["Your Name <your.email@example.com>"]
packages = [
    { include = "shared_models" },
    { include = "assistant_service" },
    { include = "rest_service" },
    { include = "google_calendar_service" },
    { include = "cron_service" },
    { include = "telegram_bot_service" },
]

[tool.poetry.dependencies]
python = "^3.11"
pydantic = "^2.4.2"
# Common production dependencies

[tool.poetry.group.dev.dependencies]
black = "^23.10.1"
isort = "^5.12.0"
flake8 = "^6.1.0"
# Common development dependencies

[tool.poetry.group.test.dependencies]
pytest = "^7.4.3"
pytest-asyncio = "^0.21.1"
# Common test dependencies
```

### 4.2 Service-Specific pyproject.toml
```toml
[tool.poetry]
name = "assistant-service"
version = "0.1.0"
description = "Assistant Service"
authors = ["Your Name <your.email@example.com>"]

[tool.poetry.dependencies]
python = "^3.11"
smart-assistant = { path = "..", develop = true }
# Service-specific production dependencies

[tool.poetry.group.dev.dependencies]
smart-assistant = { path = "..", develop = true }
# Service-specific development dependencies

[tool.poetry.group.test.dependencies]
smart-assistant = { path = "..", develop = true }
# Service-specific test dependencies
```

### 4.3 Dockerfile Example
```dockerfile
# Build stage
FROM python:3.11-slim as builder

WORKDIR /app
COPY pyproject.toml poetry.lock ./
COPY shared_models ./shared_models
COPY assistant_service ./assistant_service

RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev --no-interaction --no-ansi

# Production stage
FROM python:3.11-slim

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY assistant_service/src ./src

CMD ["python", "-m", "src.main"]
```

## 5. Benefits

### 5.1 Development
- Consistent dependency management
- Standardized linting and formatting
- Shared code quality tools
- Simplified local development

### 5.2 Build Process
- Smaller production images
- Deterministic builds
- Faster build times
- Better dependency resolution

### 5.3 Maintenance
- Centralized dependency updates
- Easier version management
- Better dependency tracking
- Simplified testing setup

## 6. Migration Plan

1. Create root pyproject.toml
2. Set up shared_models package
3. Create service-specific pyproject.toml files
4. Update Dockerfiles
5. Migrate dependencies from requirements.txt
6. Update CI/CD pipeline
7. Test and validate

## 7. Best Practices

### 7.1 Dependency Management
- Use exact versions in poetry.lock
- Regular dependency updates
- Clear separation of dev/test/prod dependencies
- Minimal production dependencies

### 7.2 Docker Optimization
- Multi-stage builds
- Minimal base images
- Layer caching
- Security scanning

### 7.3 Development Workflow
- Local Poetry environments
- Pre-commit hooks
- Automated testing
- Documentation updates 