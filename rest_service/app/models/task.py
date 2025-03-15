from typing import Optional
import enum
from sqlmodel import Field, Relationship
from .base import BaseModel
from .user import TelegramUser

class TaskStatus(str, enum.Enum):
    ACTIVE = "Активно"
    CANCELLED = "Отменено"
    DONE = "Готово"

class Task(BaseModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: str
    status: TaskStatus = Field(default=TaskStatus.ACTIVE)
    user_id: Optional[int] = Field(default=None, foreign_key="telegramuser.id")
    
    # Relationships
    user: Optional[TelegramUser] = Relationship(back_populates="tasks") 