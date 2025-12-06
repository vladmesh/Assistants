from sqlmodel import Field

from .base import BaseModel


class GlobalSettings(BaseModel, table=True):
    # We use id=1 as a constant for the single row
    id: int | None = Field(default=1, primary_key=True)
    summarization_prompt: str = Field(
        default="Summarize the conversation.",
        description="The prompt used for summarizing conversation history.",
    )
    context_window_size: int = Field(
        default=4096, description="Maximum token limit for the context window."
    )

    # --- Memory Extraction Settings ---
    memory_extraction_enabled: bool = Field(
        default=True,
        description="Whether automatic memory extraction is enabled.",
    )
    memory_extraction_interval_hours: int = Field(
        default=24,
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
        description="Similarity threshold for deduplication.",
    )
    memory_update_threshold: float = Field(
        default=0.95,
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
        description="Maximum memories per user (for retention policy).",
    )
    memory_retrieve_limit: int = Field(
        default=5,
        description="Default number of memories to retrieve.",
    )
    memory_retrieve_threshold: float = Field(
        default=0.6,
        description="Default similarity threshold for retrieval.",
    )
    # created_at and updated_at are inherited from BaseModel
