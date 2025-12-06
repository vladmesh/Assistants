import datetime

from pydantic import ConfigDict, Field

from .base import BaseSchema


class GlobalSettingsBase(BaseSchema):
    model_config = ConfigDict(from_attributes=True)
    summarization_prompt: str = Field(
        ..., description="The prompt used for summarizing conversation history."
    )
    context_window_size: int = Field(
        ..., gt=0, description="Maximum token limit for the context window (> 0)."
    )

    # --- Memory Extraction Settings ---
    memory_extraction_enabled: bool = Field(
        default=True,
        description="Whether automatic memory extraction is enabled.",
    )
    memory_extraction_interval_hours: int = Field(
        default=24,
        gt=0,
        description="How often to run batch extraction (in hours).",
    )
    memory_extraction_model: str = Field(
        default="gpt-4o-mini",
        description="LLM model for fact extraction.",
    )
    memory_extraction_provider: str = Field(
        default="openai",
        description="Provider for extraction: openai, google, anthropic.",
    )

    # --- Deduplication Settings ---
    memory_dedup_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Similarity threshold for deduplication.",
    )
    memory_update_threshold: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Similarity threshold for updating existing fact.",
    )

    # --- Embedding Settings ---
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="Model for generating embeddings.",
    )
    embedding_provider: str = Field(
        default="openai",
        description="Provider for embeddings.",
    )

    # --- Limits ---
    max_memories_per_user: int = Field(
        default=1000,
        gt=0,
        description="Maximum memories per user (for retention policy).",
    )
    memory_retrieve_limit: int = Field(
        default=5,
        gt=0,
        description="Default number of memories to retrieve.",
    )
    memory_retrieve_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Default similarity threshold for retrieval.",
    )


class GlobalSettingsRead(GlobalSettingsBase):
    id: int
    updated_at: datetime.datetime


class GlobalSettingsUpdate(BaseSchema):
    summarization_prompt: str | None = Field(
        default=None,
        description="The prompt used for summarizing conversation history.",
    )
    context_window_size: int | None = Field(
        default=None,
        gt=0,
        description="Maximum token limit for the context window (> 0).",
    )

    # --- Memory Extraction Settings ---
    memory_extraction_enabled: bool | None = Field(
        default=None,
        description="Whether automatic memory extraction is enabled.",
    )
    memory_extraction_interval_hours: int | None = Field(
        default=None,
        gt=0,
        description="How often to run batch extraction (in hours).",
    )
    memory_extraction_model: str | None = Field(
        default=None,
        description="LLM model for fact extraction.",
    )
    memory_extraction_provider: str | None = Field(
        default=None,
        description="Provider for extraction: openai, google, anthropic.",
    )

    # --- Deduplication Settings ---
    memory_dedup_threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Similarity threshold for deduplication.",
    )
    memory_update_threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Similarity threshold for updating existing fact.",
    )

    # --- Embedding Settings ---
    embedding_model: str | None = Field(
        default=None,
        description="Model for generating embeddings.",
    )
    embedding_provider: str | None = Field(
        default=None,
        description="Provider for embeddings.",
    )

    # --- Limits ---
    max_memories_per_user: int | None = Field(
        default=None,
        gt=0,
        description="Maximum memories per user (for retention policy).",
    )
    memory_retrieve_limit: int | None = Field(
        default=None,
        gt=0,
        description="Default number of memories to retrieve.",
    )
    memory_retrieve_threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Default similarity threshold for retrieval.",
    )
