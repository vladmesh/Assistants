from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Column
from sqlmodel import Field, Relationship

from .base import BaseModel
from .calendar import CalendarCredentials
from .reminder import Reminder

if TYPE_CHECKING:
    from .message import Message
    from .user_secretary import UserSecretaryLink


class TelegramUser(BaseModel, table=True):
    """Represents a Telegram user interacting with the assistant."""

    id: int | None = Field(default=None, primary_key=True)
    telegram_id: int = Field(sa_column=Column(BigInteger, unique=True, nullable=False))
    username: str | None
    timezone: str | None = Field(default=None, index=True)  # User timezone
    preferred_name: str | None = Field(
        default=None
    )  # How the user wants to be addressed

    # Relationships
    calendar_credentials: CalendarCredentials | None = Relationship(
        back_populates="user"
    )
    secretary_links: list["UserSecretaryLink"] = Relationship(  # noqa: F821
        back_populates="user", sa_relationship_kwargs={"lazy": "selectin"}
    )
    reminders: list[Reminder] = Relationship(back_populates="user")
    messages: list["Message"] = Relationship(back_populates="user")
