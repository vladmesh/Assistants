from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Rag Service Settings."""

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "DEBUG"
    API_PORT: int = 8002
    QDRANT_HOST: str = "qdrant"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION_NAME: str = "rag_data"

    # REST Service for Memory V2
    REST_SERVICE_URL: str = "http://rest_service:8000"

    # OpenAI for embeddings
    OPENAI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
