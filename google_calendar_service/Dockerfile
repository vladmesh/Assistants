FROM python:3.11-slim

WORKDIR /

ENV PYTHONPATH=/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=1.7.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    cd /usr/local/bin && \
    ln -s /opt/poetry/bin/poetry && \
    poetry --version

# Copy shared_models first
COPY shared_models/ /shared_models/

# Copy poetry files
COPY google_calendar_service/pyproject.toml google_calendar_service/poetry.lock* ./

# Install dependencies
RUN poetry install --no-interaction --no-ansi --no-root

# Copy source code
COPY google_calendar_service/src/ /src/

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"] 