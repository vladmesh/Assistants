import os
from typing import Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # REST Service URL
    REST_SERVICE_URL: str = Field(default="http://rest_service:8000")

    # Logging
    LOG_LEVEL: str = Field(default="INFO")


# Создаем экземпляр настроек
settings = Settings()
