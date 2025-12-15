import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for the Telegram bot service."""

    # Telegram settings
    telegram_token: str
    telegram_rate_limit: int = 30  # requests per second

    # Logging
    log_level: str = "INFO"
    log_json_format: bool = True

    # Metrics
    metrics_port: int = 8080

    # Redis settings
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0
    input_queue: str = os.getenv("REDIS_QUEUE_TO_SECRETARY", "queue:to_secretary")
    assistant_output_queue: str = os.getenv(
        "REDIS_QUEUE_TO_TELEGRAM", "queue:to_telegram"
    )
    input_stream_group: str = os.getenv("REDIS_INPUT_STREAM_GROUP", "assistant_input")
    output_stream_group: str = os.getenv(
        "REDIS_OUTPUT_STREAM_GROUP", "assistant_output"
    )
    stream_consumer: str = os.getenv(
        "REDIS_STREAM_CONSUMER", os.getenv("HOSTNAME", "telegram_consumer")
    )
    user_messages_prefix: str = "user_messages:"

    # REST service settings
    rest_service_url: str = "http://rest_service:8000"

    # Application settings
    update_interval: float = 1.0  # seconds
    batch_size: int = 100  # number of updates to process at once

    # Redis connection settings
    redis_settings: dict = {
        "encoding": "utf-8",
        "decode_responses": False,
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


settings = Settings()
