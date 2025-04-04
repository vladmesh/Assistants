# Build stage
FROM python:3.11-slim as builder

WORKDIR /

# Install poetry
RUN pip install poetry

# Copy dependency files
COPY assistant_service/pyproject.toml assistant_service/poetry.lock ./assistant_service/
COPY shared_models ./shared_models

# Configure poetry and install dependencies
RUN poetry config virtualenvs.create false && \
    cd assistant_service && \
    poetry install --only main --no-interaction --no-ansi --no-root

# Production stage
FROM python:3.11-slim

WORKDIR /

ENV PYTHONPATH=/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy application code
COPY assistant_service/src/ /src/

# Run the application
CMD ["python", "src/main.py"]
