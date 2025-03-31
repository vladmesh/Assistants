"""User-Secretary relationship model"""

from typing import Optional
from datetime import datetime
from uuid import UUID, uuid4
from sqlmodel import Field, Relationship
from .base import BaseModel
from .user import TelegramUser
from .assistant import Assistant


class UserSecretaryLink(BaseModel, table=True):
    """Model for linking users with their chosen secretary assistants"""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: int = Field(foreign_key="telegramuser.id")
    secretary_id: UUID = Field(foreign_key="assistant.id")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    user: "TelegramUser" = Relationship(
        back_populates="secretary_links", sa_relationship_kwargs={"lazy": "selectin"}
    )
    secretary: "Assistant" = Relationship(
        back_populates="user_links", sa_relationship_kwargs={"lazy": "selectin"}
    )
