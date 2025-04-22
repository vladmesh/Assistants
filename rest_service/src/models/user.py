from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import BigInteger, Column
from sqlmodel import Field, Relationship, SQLModel

from .base import BaseModel
from .calendar import CalendarCredentials
from .reminder import Reminder

if TYPE_CHECKING:
    from .user_fact import UserFact
    from .user_secretary import UserSecretaryLink
    from .user_summary import UserSummary


class TelegramUser(BaseModel, table=True):
    """Represents a Telegram user interacting with the assistant."""

    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_id: int = Field(sa_column=Column(BigInteger, unique=True, nullable=False))
    username: Optional[str]
    timezone: Optional[str] = Field(default=None, index=True)  # User timezone
    preferred_name: Optional[str] = Field(
        default=None
    )  # How the user wants to be addressed

    # Relationships
    calendar_credentials: Optional[CalendarCredentials] = Relationship(
        back_populates="user"
    )
    secretary_links: List["UserSecretaryLink"] = Relationship(  # noqa: F821
        back_populates="user", sa_relationship_kwargs={"lazy": "selectin"}
    )
    reminders: List[Reminder] = Relationship(back_populates="user")
    user_facts: List["UserFact"] = Relationship(back_populates="user")
    summaries: List["UserSummary"] = Relationship(back_populates="user")
