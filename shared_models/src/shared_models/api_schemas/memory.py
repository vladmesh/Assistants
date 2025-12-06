from datetime import datetime
from uuid import UUID

from .base import BaseSchema, TimestampSchema


class MemoryBase(BaseSchema):
    user_id: int
    assistant_id: UUID | None = None
    text: str
    memory_type: str
    source_message_id: UUID | None = None
    importance: int = 1
    embedding: list[float] | None = None


class MemoryCreate(MemoryBase):
    pass


class MemoryUpdate(BaseSchema):
    text: str | None = None
    memory_type: str | None = None
    importance: int | None = None
    last_accessed_at: datetime | None = None
    embedding: list[float] | None = None


class MemoryRead(MemoryBase, TimestampSchema):
    id: UUID
    last_accessed_at: datetime
