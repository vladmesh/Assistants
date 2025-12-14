"""Configuration for cron service."""

import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Cron service settings."""

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_JSON_FORMAT: bool = True

    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_QUEUE_TO_SECRETARY: str = os.getenv(
        "REDIS_QUEUE_TO_SECRETARY", "queue:to_secretary"
    )
    REDIS_QUEUE_TO_TELEGRAM: str = os.getenv(
        "REDIS_QUEUE_TO_TELEGRAM", "queue:to_telegram"
    )

    # REST service
    REST_SERVICE_URL: str = "http://rest_service:8000"


settings = Settings()
