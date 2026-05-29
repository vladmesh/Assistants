# Docker Templates and Checklist

## File Templates

### 1. Dockerfile (production)
```dockerfile
# Build stage
FROM python:3.11-slim as builder

WORKDIR /

# Install poetry
RUN pip install --no-cache-dir poetry==1.8.3

# Copy dependency files
COPY service_name/pyproject.toml service_name/poetry.lock* ./service_name/
COPY shared_models/pyproject.toml shared_models/poetry.lock* ./shared_models/
COPY shared_models/src/ ./shared_models/src/

# Configure poetry and install dependencies
RUN poetry config virtualenvs.create false && \
    cd service_name && \
    poetry install --only main --no-interaction --no-ansi --no-root

# Production stage
FROM python:3.11-slim

WORKDIR /

ENV PYTHONPATH=/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install system dependencies (if needed)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copy application code
COPY shared_models/ ./shared_models/
COPY service_name/src/ /src/

# Copy additional files (if any)
# COPY service_name/alembic/ ./alembic/  # if there are migrations
# COPY service_name/manage.py ./manage.py  # if there is a manage.py
# COPY service_name/alembic.ini ./alembic.ini  # if there is an alembic.ini

CMD ["python", "src/main.py"]
```

### 2. Dockerfile.test
```dockerfile
# Build stage
FROM python:3.11-slim as builder

WORKDIR /

# Install poetry
RUN pip install --no-cache-dir poetry==1.8.3

# Copy dependency files
COPY service_name/pyproject.toml service_name/poetry.lock* ./service_name/
COPY shared_models/pyproject.toml shared_models/poetry.lock* ./shared_models/
COPY shared_models/src/ ./shared_models/src/

# Configure poetry and install dependencies
RUN poetry config virtualenvs.create false && \
    cd service_name && \
    poetry install --only main,test --no-interaction --no-ansi --no-root

# Test stage
FROM python:3.11-slim

WORKDIR /

ENV PYTHONPATH=/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TESTING=1

# Install system dependencies (if needed)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copy application code and tests
COPY shared_models/ ./shared_models/
COPY service_name/src/ /src/
COPY service_name/tests/ /tests/

CMD ["pytest", "-v", "--cov=src", "--cov-report=term-missing", "/tests/"]
```

### 3. docker-compose.yml (service in the shared compose)
```yaml
service_name:
  build:
    context: .
    dockerfile: service_name/Dockerfile
  container_name: service-name
  environment:
    - SERVICE_VAR1=${SERVICE_VAR1}
    - SERVICE_VAR2=${SERVICE_VAR2}
  env_file:
    - .env
  ports:
    - "8000:8000"  # if needed
  volumes:
    - ./service_name/src:/src  # for development
  depends_on:
    - redis:
      condition: service_healthy
    - db:
      condition: service_healthy
  networks:
    - app_network
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    interval: 30s
    timeout: 10s
    retries: 3
```

### 4. docker-compose.test.yml
```yaml
services:
  test:
    build:
      context: ..
      dockerfile: service_name/Dockerfile.test
    environment:
      - TESTING=1
      - PYTHONPATH=/src
      - PYTHONUNBUFFERED=1
      - PYTHONDONTWRITEBYTECODE=1
      # Service-specific variables
      - SERVICE_VAR1=test_value1
      - SERVICE_VAR2=test_value2
    env_file:
      - ./tests/.env.test
    depends_on:
      - test-db:
        condition: service_healthy
      - redis:
        condition: service_healthy

  test-db:
    image: postgres:16
    environment:
      - POSTGRES_USER=test_user
      - POSTGRES_PASSWORD=test_password
      - POSTGRES_DB=test_db
    volumes:
      - test_db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test_user -d test_db"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7.2-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3

volumes:
  test_db_data:
```

## Service Review Checklist
### General
- [x] An up-to-date `.dockerignore` for all builds exists at the repo root
- [x] Dockerfile order: pyproject/lock → shared_models (pyproject+src) → install → code/tests

### assistant_service
- [x] Dockerfile matches the template
- [x] Dockerfile.test matches the template
- [x] The block in the shared docker-compose.yml matches the template
- [x] docker-compose.test.yml matches the template

### rest_service
- [x] Dockerfile matches the template
- [x] Dockerfile.test matches the template
- [x] The block in the shared docker-compose.yml matches the template
- [x] docker-compose.test.yml matches the template

### google_calendar_service
- [x] Dockerfile matches the template
- [x] Dockerfile.test matches the template
- [x] The block in the shared docker-compose.yml matches the template
- [x] docker-compose.test.yml matches the template

### cron_service
- [x] Dockerfile matches the template
- [x] Dockerfile.test matches the template
- [x] The block in the shared docker-compose.yml matches the template
- [x] docker-compose.test.yml matches the template

### telegram_bot_service
- [x] Dockerfile matches the template
- [x] Dockerfile.test matches the template
- [x] The block in the shared docker-compose.yml matches the template
- [x] docker-compose.test.yml matches the template

## Notes
1. When reviewing each file, account for the specifics of the service.
2. Some services may not require all components (e.g., not all of them need a database).
3. Ports and environment variables must be adapted to the specific service.
4. The healthcheck must be configured to match the service's API.
5. When using Poetry, make sure `poetry.lock` is up to date.
6. For local dependencies (e.g., shared_models), do not use the `develop=true` flag in `pyproject.toml`. 