"""BatchJob model for tracking LLM batch API jobs."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import TEXT, Column
from sqlmodel import Field

from .base import BaseModel


class BatchJob(BaseModel, table=True):
    """Tracks batch API jobs for memory extraction.

    Used to track the status of batch requests submitted to LLM providers
    (OpenAI, Anthropic, Google) for fact extraction from conversations.
    """

    __tablename__ = "batch_jobs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    batch_id: str = Field(index=True, description="Batch ID from LLM provider")
    user_id: int = Field(
        foreign_key="telegramuser.id", index=True, description="User being processed"
    )
    assistant_id: UUID | None = Field(
        default=None,
        foreign_key="assistant.id",
        index=True,
        description="Assistant context (None = all)",
    )

    # Job metadata
    job_type: str = Field(
        default="memory_extraction", index=True, description="Type of batch job"
    )
    status: str = Field(
        default="pending",
        index=True,
        description="Job status: pending, processing, completed, failed",
    )
    provider: str = Field(
        default="openai", description="LLM provider: openai, anthropic, google"
    )
    model: str = Field(default="gpt-4o-mini", description="Model used for extraction")

    # Processing info
    messages_processed: int = Field(
        default=0, description="Number of messages in batch"
    )
    facts_extracted: int = Field(default=0, description="Number of facts extracted")
    completed_at: datetime | None = Field(
        default=None, description="When job completed"
    )
    error_message: str | None = Field(
        default=None,
        sa_column=Column(TEXT),
        description="Error message if failed",
    )

    # Input data reference
    since_timestamp: datetime | None = Field(
        default=None, description="Start of conversation window"
    )
    until_timestamp: datetime | None = Field(
        default=None, description="End of conversation window"
    )
