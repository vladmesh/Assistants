"""Application configuration"""

import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    ASYNC_DATABASE_URL: str = os.getenv(
        "ASYNC_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@db:5432/postgres"
    )
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # Redis settings
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    # Cache settings
    CACHE_ENABLED: bool = os.getenv("CACHE_ENABLED", "true").lower() == "true"
    CACHE_PREFIX: str = os.getenv("CACHE_PREFIX", "rest_api")

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_JSON_FORMAT: bool = True
    ENVIRONMENT: str = "production"

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


settings = Settings()
