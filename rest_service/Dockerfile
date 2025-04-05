# Build stage
FROM python:3.11-slim as builder

WORKDIR /

# Install poetry
RUN pip install poetry

# Copy dependency files
COPY rest_service/pyproject.toml rest_service/poetry.lock* ./rest_service/
COPY shared_models ./shared_models

# Configure poetry and install dependencies
RUN poetry config virtualenvs.create false && \
    cd rest_service && \
    poetry install --only main --no-interaction --no-ansi --no-root

# Production stage
FROM python:3.11-slim

WORKDIR /

ENV PYTHONPATH=/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copy application code
COPY rest_service/src/ /src/

# Копирование дополнительных файлов
COPY rest_service/alembic/ ./alembic/
COPY rest_service/manage.py ./manage.py
COPY rest_service/alembic.ini ./alembic.ini

CMD ["python", "src/main.py"]
