from datetime import datetime
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


class CalendarCredentials(SQLModel, table=True):
    """Represents Google Calendar API credentials stored for a user."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="telegramuser.id")
    access_token: str
    refresh_token: str
    token_expiry: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    user: Optional["TelegramUser"] = Relationship(  # noqa: F821
        back_populates="calendar_credentials"
    )
