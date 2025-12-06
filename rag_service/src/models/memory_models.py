"""Models for Memory V2 operations."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MemorySearchQuery(BaseModel):
    """Query for searching memories by text."""

    query: str = Field(..., description="Text query to search for")
    user_id: int = Field(..., description="User ID to filter memories")
    limit: int = Field(default=10, description="Maximum results to return")
    threshold: float = Field(default=0.7, description="Similarity threshold")


class MemoryCreateRequest(BaseModel):
    """Request to create a new memory."""

    user_id: int = Field(..., description="User ID")
    text: str = Field(..., description="Memory text content")
    memory_type: str = Field(
        ...,
        description="Type: user_fact | conversation_insight | preference | event",
    )
    assistant_id: UUID | None = Field(
        default=None,
        description="Assistant ID (None = shared)",
    )
    importance: int = Field(default=1, description="1-10 importance scale")


class MemoryResponse(BaseModel):
    """Memory response from REST service."""

    id: UUID
    user_id: int
    assistant_id: UUID | None = None
    text: str
    memory_type: str
    importance: int
    last_accessed_at: datetime
    created_at: datetime
    updated_at: datetime


class MemorySearchResult(BaseModel):
    """Single memory search result."""

    id: UUID
    user_id: int
    text: str
    memory_type: str
    importance: int
