from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Optional
from uuid import UUID

from sqlalchemy import TEXT, TIMESTAMP, Column, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

from .base import BaseModel, get_utc_now

if TYPE_CHECKING:
    from .assistant import Assistant
    from .user import TelegramUser # Assuming user model is TelegramUser based on plan
    from .user_summary import UserSummary


class Message(BaseModel, table=True):
    __tablename__ = "messages"

    id: Optional[int] = Field(default=None, primary_key=True, sa_column_kwargs={"autoincrement": True}) # BIGSERIAL
    user_id: int = Field(foreign_key="telegramuser.id", index=True)
    assistant_id: UUID = Field(foreign_key="assistant.id", index=True)
    timestamp: datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(TIMESTAMP(timezone=True), index=True) # TIMESTAMPTZ с индексом
    )
    role: str = Field(index=True)
    content: str = Field(sa_column=Column(TEXT))
    content_type: str = Field(default='text')
    tool_call_id: Optional[UUID] = Field(default=None, index=True)
    status: str = Field(default='active', index=True)
    summary_id: Optional[int] = Field(default=None, foreign_key="user_summaries.id")
    meta_data: Optional[dict] = Field(sa_column=Column(JSONB))

    # Relationships
    user: "TelegramUser" = Relationship(back_populates="messages")
    assistant: "Assistant" = Relationship(back_populates="messages")
    summary: Optional["UserSummary"] = Relationship(back_populates="messages")

    __table_args__ = (
        Index("ix_messages_user_id_assistant_id_id", "user_id", "assistant_id", "id"),
        # Other indexes like (user_id, timestamp), (assistant_id, timestamp) might be beneficial
        # depending on query patterns, but let's stick to the plan for now.
        # The plan mentions: user_id, assistant_id, timestamp, tool_call_id, status, (user_id, assistant_id, id)
        # Individual indexes on user_id, assistant_id, timestamp, tool_call_id, status are created by `index=True` on Fields.
    )
