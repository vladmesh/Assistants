from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import TEXT, Column
from sqlmodel import Field, Relationship

# Import BaseModel
from .base import BaseModel

if TYPE_CHECKING:
    from .assistant import Assistant
    from .user import TelegramUser


# Inherit from BaseModel instead of just SQLModel
class UserSummary(BaseModel, table=True):
    """
    Represents a summarized context for a specific user interacting with a specific secretary assistant.
    """

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: int = Field(foreign_key="telegramuser.id", index=True)
    secretary_id: UUID = Field(foreign_key="assistant.id", index=True)
    summary_text: str = Field(
        sa_column=Column(TEXT)
    )  # Use TEXT for potentially long summaries
    # Remove created_at and updated_at as they are inherited from BaseModel
    # created_at: datetime = Field(default_factory=datetime.utcnow)
    # updated_at: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow})

    __tablename__ = "user_summaries"

    # Relationships
    user: "TelegramUser" = Relationship(back_populates="summaries")
    secretary: "Assistant" = Relationship(back_populates="user_summaries")
