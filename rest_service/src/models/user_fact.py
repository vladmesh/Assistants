from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

from .base import BaseModel

if TYPE_CHECKING:
    from .user import TelegramUser  # Import needed for relationship type hinting


class UserFact(BaseModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: int = Field(foreign_key="telegramuser.id", index=True)
    fact: str = Field(index=True)

    # Оставляем только связь с пользователем
    user: "TelegramUser" = Relationship(back_populates="user_facts")

    class Config:
        table_name = "user_facts"
