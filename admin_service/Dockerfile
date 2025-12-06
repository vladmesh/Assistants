# Build stage
FROM python:3.11-slim as builder

WORKDIR /

# Install poetry
RUN pip install --no-cache-dir poetry==1.8.3

# Copy dependency files
COPY admin_service/pyproject.toml admin_service/poetry.lock* ./admin_service/
COPY shared_models/pyproject.toml shared_models/poetry.lock* ./shared_models/
COPY shared_models/src/ ./shared_models/src/

# Configure poetry and install dependencies
RUN poetry config virtualenvs.create false && \
    cd admin_service && \
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
COPY shared_models/ ./shared_models/
COPY admin_service/src/ /src/

CMD ["streamlit", "run", "src/main.py", "--server.port=8501", "--server.address=0.0.0.0"] 