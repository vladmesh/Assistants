import os
from typing import Dict

import structlog
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = structlog.get_logger()


class Settings(BaseSettings):
    """Configuration settings for the Telegram bot service."""

    # Telegram settings
    telegram_token: str
    telegram_rate_limit: int = 30  # requests per second

    # Redis settings
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0
    input_queue: str = os.getenv("REDIS_QUEUE_TO_SECRETARY", "queue:to_secretary")
    assistant_output_queue: str = os.getenv(
        "REDIS_QUEUE_TO_TELEGRAM", "queue:to_telegram"
    )
    user_messages_prefix: str = "user_messages:"

    # REST service settings
    rest_service_url: str = "http://rest_service:8000"

    # Application settings
    update_interval: float = 1.0  # seconds
    batch_size: int = 100  # number of updates to process at once

    # Redis connection settings
    redis_settings: Dict = {
        "encoding": "utf-8",
        "decode_responses": True,
        "retry_on_timeout": True,
        "socket_keepalive": True,
    }

    @property
    def redis_url(self) -> str:
        """Get Redis connection URL."""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    def get_user_queue(self, user_id: str) -> str:
        """Get queue name for specific user."""
        return f"{self.user_messages_prefix}{user_id}"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


try:
    settings = Settings()
    logger.info(
        "Settings loaded",
        redis_host=settings.redis_host,
        redis_port=settings.redis_port,
        rest_service_url=settings.rest_service_url,
        redis_url=settings.redis_url,
        input_queue=settings.input_queue,
        assistant_output_queue=settings.assistant_output_queue,
    )
except Exception as e:
    logger.error("Error loading settings", error=str(e))
    raise
