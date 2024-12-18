from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
import enum
from sqlalchemy import event
from datetime import datetime

class BaseModel(SQLModel):
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

# События для автоматического обновления
@event.listens_for(BaseModel, "before_update", propagate=True)
def before_update(mapper, connection, target):
    target.updated_at = datetime.utcnow()

class TaskStatus(str, enum.Enum):
    ACTIVE = "Активно"
    CANCELLED = "Отменено"
    DONE = "Готово"

class TelegramUser(BaseModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_id: int = Field(unique=True, nullable=False)
    username: Optional[str]
    tasks: List["Task"] = Relationship(back_populates="user")

class Task(BaseModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: str
    status: TaskStatus = Field(default=TaskStatus.ACTIVE)
    user_id: Optional[int] = Field(default=None, foreign_key="telegramuser.id")
    user: Optional[TelegramUser] = Relationship(back_populates="tasks")
