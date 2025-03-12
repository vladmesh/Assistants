from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache

class Settings(BaseSettings):
    """Application settings"""
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    OPENAI_API_KEY: str
    OPEN_API_SECRETAR_ID: str
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "assistant"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    INPUT_QUEUE: str = "telegram_input_queue"
    OUTPUT_QUEUE: str = "telegram_output_queue"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings() 