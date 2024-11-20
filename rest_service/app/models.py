from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
import enum

class TaskStatus(str, enum.Enum):
    CREATED = "Создано"
    IN_PROGRESS = "В процессе"
    CANCELLED = "Отменено"
    DONE = "Готово"

class TelegramUser(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_id: str = Field(unique=True, nullable=False)
    username: Optional[str]
    tasks: List["Task"] = Relationship(back_populates="user")

class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    text: str
    status: TaskStatus = Field(default=TaskStatus.CREATED)
    user_id: Optional[int] = Field(default=None, foreign_key="telegramuser.id")
    user: Optional[TelegramUser] = Relationship(back_populates="tasks")
