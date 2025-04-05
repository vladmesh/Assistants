# Build stage
FROM python:3.11-slim as builder

WORKDIR /

# Install poetry
RUN pip install poetry

# Copy dependency files
COPY cron_service/pyproject.toml cron_service/poetry.lock* ./cron_service/
COPY shared_models ./shared_models

# Configure poetry and install dependencies
RUN poetry config virtualenvs.create false && \
    cd cron_service && \
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
COPY cron_service/src/ /src/

CMD ["python", "src/main.py"]
