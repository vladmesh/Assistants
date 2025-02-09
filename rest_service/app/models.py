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

class CronJobType(str, enum.Enum):
    NOTIFICATION = "notification"
    SCHEDULE = "schedule"

class CronJobStatus(str, enum.Enum):
    CREATED = "created"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"

class TelegramUser(BaseModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_id: int = Field(unique=True, nullable=False)
    chat_id: int = Field(unique=True, nullable=False)
    username: Optional[str]
    tasks: List["Task"] = Relationship(back_populates="user")
    cronjobs: List["CronJob"] = Relationship(back_populates="user")

class Task(BaseModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: str
    status: TaskStatus = Field(default=TaskStatus.ACTIVE)
    user_id: Optional[int] = Field(default=None, foreign_key="telegramuser.id")
    user: Optional[TelegramUser] = Relationship(back_populates="tasks")

class CronJob(BaseModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    type: CronJobType = Field(default=CronJobType.NOTIFICATION)
    cron_expression: str
    user_id: Optional[int] = Field(default=None, foreign_key="telegramuser.id")
    user: Optional[TelegramUser] = Relationship(back_populates="cronjobs")

class CronJobNotification(BaseModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    cron_job_id: Optional[int] = Field(default=None, foreign_key="cronjob.id")
    message: str

class CronJobRecord(BaseModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    cron_job_id: Optional[int] = Field(default=None, foreign_key="cronjob.id")
    started_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    finished_at: Optional[datetime] = None
    status: CronJobStatus = Field(default=CronJobStatus.CREATED)