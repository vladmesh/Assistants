from typing import Optional
import enum
from datetime import datetime
from sqlmodel import Field, Relationship
from .base import BaseModel


class CronJobType(str, enum.Enum):
    NOTIFICATION = "notification"
    SCHEDULE = "schedule"


class CronJobStatus(str, enum.Enum):
    CREATED = "created"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class CronJob(BaseModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    type: CronJobType = Field(default=CronJobType.NOTIFICATION)
    cron_expression: str
    user_id: Optional[int] = Field(default=None, foreign_key="telegramuser.id")
    is_active: bool = Field(default=True)

    # Relationships
    user: Optional["TelegramUser"] = Relationship(back_populates="cronjobs")


class CronJobNotification(BaseModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    cron_job_id: Optional[int] = Field(default=None, foreign_key="cronjob.id")
    message: str


class CronJobRecord(BaseModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    cron_job_id: Optional[int] = Field(default=None, foreign_key="cronjob.id")
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), nullable=False
    )
    finished_at: Optional[datetime] = None
    status: CronJobStatus = Field(default=CronJobStatus.CREATED)
