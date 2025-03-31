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


settings = Settings()
