from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import TEXT, Column
from sqlmodel import Field, Relationship

# Import BaseModel
from .base import BaseModel

if TYPE_CHECKING:
    from .assistant import Assistant
    from .message import Message
    from .user import TelegramUser


# Inherit from BaseModel instead of just SQLModel
class UserSummary(BaseModel, table=True):
    """Summarized context for a user with a secretary assistant."""

    id: int | None = Field(
        default=None, primary_key=True, sa_column_kwargs={"autoincrement": True}
    )
    user_id: int = Field(foreign_key="telegramuser.id", index=True)
    assistant_id: UUID = Field(foreign_key="assistant.id", index=True)
    summary_text: str = Field(
        sa_column=Column(TEXT)
    )  # Use TEXT for potentially long summaries
    token_count: int | None = Field(default=None, nullable=True)

    __tablename__ = "user_summaries"

    # Relationships
    user: "TelegramUser" = Relationship(back_populates="summaries")
    assistant: "Assistant" = Relationship(back_populates="user_summaries")
    messages: list["Message"] = Relationship(
        back_populates="summary",
        sa_relationship_kwargs={"foreign_keys": "[Message.summary_id]"},
    )
