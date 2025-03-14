from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    """Application settings"""
    # Basic settings
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "DEBUG"
    
    # Google OAuth settings
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str
    
    # Telegram settings
    TELEGRAM_BOT_USERNAME: str
    TELEGRAM_DEEP_LINK_URL: str = "https://t.me/{TELEGRAM_BOT_USERNAME}"
    
    # REST service settings
    REST_SERVICE_URL: str = "http://rest_service:8000"
    
    # Redis settings
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    # Queue names
    INPUT_QUEUE: str = "calendar_input_queue"
    OUTPUT_QUEUE: str = "calendar_output_queue"
    ASSISTANT_INPUT_QUEUE: str = "telegram_input_queue"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8") 