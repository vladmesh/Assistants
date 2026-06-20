"""Configuration settings for the admin panel."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Admin panel settings."""

    # REST API settings
    REST_SERVICE_URL: str = Field(default="http://rest_service:8000")

    # Logging settings
    LOG_LEVEL: str = Field(default="INFO")
    LOG_JSON_FORMAT: bool = Field(default=True)

    # Application settings
    APP_TITLE: str = "Admin Panel"
    APP_ICON: str = "🔧"
    APP_LAYOUT: str = "wide"

    # Monitoring URLs
    GRAFANA_URL: str | None = Field(default=None)
    PROMETHEUS_URL: str | None = Field(default=None)
    LOKI_URL: str | None = Field(default=None)

    # Navigation
    NAV_ITEMS: list[str] = [
        "Пользователи",
        "Ассистенты",
        "Инструменты",
        "Глобальные настройки",
        "---",
        "Логи",
        "Джобы",
        "Очереди",
        "Метрики",
    ]

    # Database settings (admin UI does not access DB directly)
    # POSTGRES_USER = os.getenv("POSTGRES_USER", "admin")

    # Admin authentication
    # Secrets (cookie key, bcrypt password hash) come from the environment and
    # are never committed. The app refuses to start if they are unset
    # (see main.py). Generate the hash with streamlit_authenticator's Hasher.
    ADMIN_USERNAME: str = Field(default="admin")
    ADMIN_NAME: str = Field(default="Admin User")
    ADMIN_EMAIL: str = Field(default="admin@example.com")
    ADMIN_PASSWORD_HASH: str = Field(default="")
    ADMIN_COOKIE_KEY: str = Field(default="")
    ADMIN_COOKIE_NAME: str = Field(default="admin_cookie")
    ADMIN_COOKIE_EXPIRY_DAYS: int = Field(default=30)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Create settings instance
settings = Settings()
