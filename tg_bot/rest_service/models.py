from typing import Optional, List
from pydantic import BaseModel
from enum import Enum


class TaskStatus(str, Enum):
    CREATED = "Создано"
    IN_PROGRESS = "В процессе"
    CANCELLED = "Отменено"
    DONE = "Готово"


class Task(BaseModel):
    id: Optional[int]
    text: Optional[str]
    status: Optional[TaskStatus] = TaskStatus.CREATED
    user_id: Optional[int]

    def update_dict(self) -> dict:
        """Возвращает словарь с изменёнными полями."""
        return {key: value for key, value in self.dict(exclude_unset=True).items() if value is not None}


class TelegramUser(BaseModel):
    id: Optional[int]
    telegram_id: str
    username: Optional[str]
    tasks: List[Task] = []
