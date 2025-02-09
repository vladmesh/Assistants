from typing import Optional, List
from pydantic import BaseModel
from enum import Enum


class TaskStatus(str, Enum):
    ACTIVE = "Активно"
    CANCELLED = "Отменено"
    DONE = "Готово"


class Task(BaseModel):
    id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = TaskStatus.ACTIVE
    user_id: Optional[int] = None

    def update_dict(self) -> dict:
        """Возвращает словарь с изменёнными полями."""
        data = {key: value for key, value in self.dict(exclude_unset=True).items() if value is not None}
        print(f"Данные для обновления: {data}")
        return data


class TelegramUser(BaseModel):
    id: Optional[int]
    telegram_id: int
    username: Optional[str]
    from pydantic import Field

    tasks: List[Task] = Field(default_factory=list)
