from typing import List, Optional

from sqlalchemy import BigInteger, Column
from sqlmodel import Field, Relationship

from .base import BaseModel


class TelegramUser(BaseModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_id: int = Field(sa_column=Column(BigInteger, unique=True, nullable=False))
    username: Optional[str]

    # Relationships
    cronjobs: List["CronJob"] = Relationship(back_populates="user")
    calendar_credentials: Optional["CalendarCredentials"] = Relationship(
        back_populates="user"
    )
    secretary_links: List["UserSecretaryLink"] = Relationship(
        back_populates="user", sa_relationship_kwargs={"lazy": "selectin"}
    )
