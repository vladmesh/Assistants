from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application settings"""
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    OPENAI_API_KEY: str
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings() 