import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""

    # Basic settings
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "DEBUG"
    HTTP_CLIENT_TIMEOUT: float = 60.0

    # API Keys (loaded from .env)
    OPENAI_API_KEY: str
    TAVILY_API_KEY: Optional[str] = None

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

    # Queue names
    INPUT_QUEUE: str = os.getenv("REDIS_QUEUE_TO_SECRETARY")
    OUTPUT_QUEUE: str = os.getenv("REDIS_QUEUE_TO_TELEGRAM")

    # Google Calendar settings
    GOOGLE_CALENDAR_CREDENTIALS: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
