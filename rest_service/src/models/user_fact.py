from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from .base import BaseModel

if TYPE_CHECKING:
    from .user import TelegramUser  # Import needed for relationship type hinting


class UserFact(BaseModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: int = Field(foreign_key="telegramuser.id", index=True)
    fact: str = Field(index=True)

    # Define the relationship if needed, e.g., to access the user from the fact
    # user: "TelegramUser" = Relationship(back_populates="facts")
