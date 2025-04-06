from typing import List, Optional

from sqlalchemy import BigInteger, Column
from sqlmodel import Field, Relationship

from .base import BaseModel
from .calendar import CalendarCredentials
from .reminder import Reminder


class TelegramUser(BaseModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_id: int = Field(sa_column=Column(BigInteger, unique=True, nullable=False))
    username: Optional[str]

    # Relationships
    calendar_credentials: Optional[CalendarCredentials] = Relationship(
        back_populates="user"
    )
    secretary_links: List["UserSecretaryLink"] = Relationship(  # noqa: F821
        back_populates="user", sa_relationship_kwargs={"lazy": "selectin"}
    )
    reminders: List[Reminder] = Relationship(back_populates="user")
