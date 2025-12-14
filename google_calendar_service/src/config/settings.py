from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""

    # Basic settings
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "DEBUG"
    LOG_JSON_FORMAT: bool = True

    # Google OAuth settings
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str
    GOOGLE_TOKEN_URI: str = "https://oauth2.googleapis.com/token"
    GOOGLE_AUTH_PROVIDER_CERT_URL: str = "https://www.googleapis.com/oauth2/v1/certs"

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
    REDIS_QUEUE_TO_SECRETARY: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
