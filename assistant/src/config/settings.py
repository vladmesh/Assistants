from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache
import os

class Settings(BaseSettings):
    """Application settings"""
    # Basic settings
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    
    # API Keys (loaded from .env)
    OPENAI_API_KEY: str
    OPEN_API_SECRETAR_ID: str
    
    # Redis settings
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    # Queue names
    INPUT_QUEUE: str = os.getenv("REDIS_QUEUE_TO_SECRETARY", "queue:to_secretary")
    OUTPUT_QUEUE: str = os.getenv("REDIS_QUEUE_TO_TELEGRAM", "queue:to_telegram")
    
    # Assistant configuration
    MAIN_ASSISTANT_TYPE: str = "openai"  # openai or llm
    MAIN_ASSISTANT_MODEL: str = "gpt-4-turbo-preview"
    SUB_ASSISTANT_TYPE: str = "llm"  # openai or llm
    SUB_ASSISTANT_MODEL: str = "gpt-4-turbo-preview"
    
    # Assistant instructions
    MAIN_ASSISTANT_INSTRUCTIONS: str = """Ты - умный секретарь-ассистент. Твоя задача - помогать пользователю в решении различных задач.
    
    Ты можешь:
    1. Отвечать на вопросы
    2. Помогать с планированием
    3. Создавать напоминания
    4. Узнавать текущее время
    5. Делегировать творческие задачи писателю
    
    Всегда отвечай на русском языке, если не указано иное."""
    
    SUB_ASSISTANT_INSTRUCTIONS: str = """Ты - специализированный ассистент, пишущий художественные тексты. Пиши красиво и выразительно.
    
    Всегда отвечай на русском языке, если не указано иное."""

    class Config:
        env_file = ".env"  # Включаем загрузку из .env для API ключей
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings() 