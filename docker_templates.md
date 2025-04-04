# Docker Templates and Checklist

## Шаблоны файлов

### 1. Dockerfile (продакшн)
```dockerfile
# Build stage
FROM python:3.11-slim as builder

WORKDIR /

# Install poetry
RUN pip install poetry

# Copy dependency files
COPY pyproject.toml poetry.lock ./
COPY shared_models ./shared_models

# Configure poetry and install dependencies
RUN poetry config virtualenvs.create false && \
    poetry install --only main --no-interaction --no-ansi

# Production stage
FROM python:3.11-slim

WORKDIR /

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy application code
COPY src/ /src/

# Копирование дополнительных файлов (если есть)
COPY alembic/ ./alembic/  # если есть миграции
COPY manage.py .          # если есть manage.py

CMD ["python", "src/main.py"]
```

### 2. Dockerfile.test
```dockerfile
# Build stage
FROM python:3.11-slim as builder

WORKDIR /

# Install poetry
RUN pip install poetry

# Copy dependency files
COPY pyproject.toml poetry.lock ./
COPY shared_models ./shared_models

# Configure poetry and install dependencies
RUN poetry config virtualenvs.create false && \
    poetry install --only main,test --no-interaction --no-ansi

# Test stage
FROM python:3.11-slim

WORKDIR /

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TESTING=1

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy application code and tests
COPY src/ /src/
COPY tests/ /tests/

CMD ["pytest", "-v", "--cov=src", "--cov-report=term-missing", "/tests/"]
```

### 3. docker-compose.yml (сервис в общем компоузе)
```yaml
service_name:
  build:
    context: ./service_name
    dockerfile: Dockerfile
  container_name: service-name
  environment:
    - SERVICE_VAR1=${SERVICE_VAR1}
    - SERVICE_VAR2=${SERVICE_VAR2}
  env_file:
    - .env
  ports:
    - "8000:8000"  # если нужно
  volumes:
    - ./service_name/src:/src  # для разработки
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
      context: .
      dockerfile: Dockerfile.test
    environment:
      - TESTING=1
      - PYTHONPATH=/src
      - PYTHONUNBUFFERED=1
      - PYTHONDONTWRITEBYTECODE=1
      # Специфичные для сервиса переменные
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
    ports:
      - "5433:5432"
    volumes:
      - test_db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test_user -d test_db"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7.2-alpine
    ports:
      - "6380:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3

volumes:
  test_db_data:
```

## Чек-лист проверки сервисов

### assistant_service
- [x] Dockerfile соответствует шаблону
- [x] Dockerfile.test соответствует шаблону
- [x] Блок в общем docker-compose.yml соответствует шаблону
- [x] docker-compose.test.yml соответствует шаблону

### rest_service
- [ ] Dockerfile соответствует шаблону
- [ ] Dockerfile.test соответствует шаблону
- [x] Блок в общем docker-compose.yml соответствует шаблону
- [x] docker-compose.test.yml соответствует шаблону

### google_calendar_service
- [ ] Dockerfile соответствует шаблону
- [ ] Dockerfile.test соответствует шаблону
- [x] Блок в общем docker-compose.yml соответствует шаблону
- [x] docker-compose.test.yml соответствует шаблону

### cron_service
- [ ] Dockerfile соответствует шаблону
- [ ] Dockerfile.test соответствует шаблону
- [x] Блок в общем docker-compose.yml соответствует шаблону
- [x] docker-compose.test.yml соответствует шаблону

### telegram_bot_service
- [ ] Dockerfile соответствует шаблону
- [ ] Dockerfile.test соответствует шаблону
- [x] Блок в общем docker-compose.yml соответствует шаблону
- [x] docker-compose.test.yml соответствует шаблону

## Примечания
1. При проверке каждого файла нужно учитывать специфику сервиса
2. Некоторые сервисы могут не требовать всех компонентов (например, не все нуждаются в базе данных)
3. Порты и переменные окружения должны быть адаптированы под конкретный сервис
4. Healthcheck должен быть настроен в соответствии с API сервиса
5. При использовании Poetry необходимо убедиться, что poetry.lock актуален
6. Для локальных зависимостей (например, shared_models) не использовать флаг develop=true в pyproject.toml 