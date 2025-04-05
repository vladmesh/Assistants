"""Configuration settings for the admin panel."""


from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Admin panel settings."""

    # REST API settings
    REST_SERVICE_URL: str = Field(default="http://rest_service:8000")

    # Logging settings
    LOG_LEVEL: str = Field(default="INFO")

    # Application settings
    APP_TITLE: str = "Admin Panel"
    APP_ICON: str = "🔧"
    APP_LAYOUT: str = "wide"

    # Navigation
    NAV_ITEMS: list[str] = ["Пользователи", "Ассистенты"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Create settings instance
settings = Settings()
