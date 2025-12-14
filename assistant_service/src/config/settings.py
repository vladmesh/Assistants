import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""

    # Basic settings
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "DEBUG"
    LOG_JSON_FORMAT: bool = True
    HTTP_CLIENT_TIMEOUT: float = 60.0

    # API Keys (loaded from .env)
    OPENAI_API_KEY: str
    TAVILY_API_KEY: str | None = None

    # Redis settings
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # REST service settings
    REST_SERVICE_HOST: str = "rest_service"  # Docker service name
    REST_SERVICE_PORT: int = 8000

    @property
    def REST_SERVICE_URL(self) -> str:
        return f"http://{self.REST_SERVICE_HOST}:{self.REST_SERVICE_PORT}"

    # RAG service settings (for Memory V2)
    RAG_SERVICE_HOST: str = "rag_service"  # Docker service name
    RAG_SERVICE_PORT: int = 8002

    @property
    def RAG_SERVICE_URL(self) -> str:
        return f"http://{self.RAG_SERVICE_HOST}:{self.RAG_SERVICE_PORT}"

    # Queue names
    INPUT_QUEUE: str = os.getenv("REDIS_QUEUE_TO_SECRETARY")
    OUTPUT_QUEUE: str = os.getenv("REDIS_QUEUE_TO_TELEGRAM")
    INPUT_STREAM_GROUP: str = os.getenv("REDIS_INPUT_STREAM_GROUP", "assistant_input")
    OUTPUT_STREAM_GROUP: str = os.getenv(
        "REDIS_OUTPUT_STREAM_GROUP", "assistant_output"
    )
    STREAM_CONSUMER: str = os.getenv(
        "REDIS_STREAM_CONSUMER", os.getenv("HOSTNAME", "assistant_consumer")
    )

    # Google Calendar settings
    GOOGLE_CALENDAR_CREDENTIALS: str | None = None

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
