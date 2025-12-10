from datetime import UTC, datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlmodel import TEXT, Column, Field

from .base import BaseModel


class Memory(BaseModel, table=True):
    """Unified memory entity for user/assistant context."""

    __tablename__ = "memories"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: int = Field(
        index=True
    )  # Foreign key to telegramuser.id handled in rest_service if needed
    assistant_id: UUID | None = Field(
        default=None, index=True, description="None = shared across all assistants"
    )

    # Content
    text: str = Field(sa_column=Column(TEXT), description="What to remember")
    embedding: list[float] | None = Field(
        default=None,
        sa_column=Column(Vector(1536)),  # text-embedding-3-small
        description="Vector representation for semantic search",
    )

    # Classification
    memory_type: str = Field(
        index=True,
        description=(
            "user_fact | conversation_insight | preference | "
            "event | extracted_knowledge"
        ),
    )

    # Metadata
    source_message_id: UUID | None = Field(
        default=None, description="Link to origin message"
    )
    importance: int = Field(default=1, description="1-10 scale for retention policy")
    last_accessed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
