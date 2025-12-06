from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import TEXT, TIMESTAMP, Column, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship

from .base import BaseModel, get_utc_now

if TYPE_CHECKING:
    from .assistant import Assistant
    from .user import TelegramUser


class Message(BaseModel, table=True):
    __tablename__ = "messages"

    id: int | None = Field(
        default=None, primary_key=True, sa_column_kwargs={"autoincrement": True}
    )
    user_id: int = Field(foreign_key="telegramuser.id", index=True)
    assistant_id: UUID = Field(foreign_key="assistant.id", index=True)
    timestamp: datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(TIMESTAMP(timezone=True), index=True),
    )
    role: str = Field(index=True)
    content: str = Field(sa_column=Column(TEXT))
    content_type: str = Field(default="text")
    tool_call_id: str | None = Field(default=None, index=True)
    status: str = Field(default="active", index=True)
    meta_data: dict | None = Field(sa_column=Column(JSONB))

    # Relationships
    user: "TelegramUser" = Relationship(back_populates="messages")
    assistant: "Assistant" = Relationship(back_populates="messages")

    __table_args__ = (
        Index("ix_messages_user_id_assistant_id_id", "user_id", "assistant_id", "id"),
    )
