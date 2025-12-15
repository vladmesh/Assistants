"""JobExecution model for tracking cron job executions."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import TEXT, Column
from sqlmodel import Field

from .base import BaseModel


class JobStatus(str, Enum):
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobExecution(BaseModel, table=True):
    """Tracks execution history of cron jobs.

    Used to monitor and debug scheduled tasks like reminders,
    memory extraction, and other background jobs.
    """

    __tablename__ = "job_executions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    job_id: str = Field(index=True, description="Job ID in APScheduler")
    job_name: str = Field(description="Human-readable job name")
    job_type: str = Field(
        index=True,
        description="Job type: reminder, memory_extraction, update_reminders",
    )

    status: JobStatus = Field(default=JobStatus.SCHEDULED, index=True)

    scheduled_at: datetime = Field(description="When the job was scheduled to run")
    started_at: datetime | None = Field(default=None, description="When job started")
    finished_at: datetime | None = Field(default=None, description="When job finished")
    duration_ms: int | None = Field(
        default=None, description="Execution duration in milliseconds"
    )

    user_id: int | None = Field(default=None, index=True, description="For user jobs")
    reminder_id: int | None = Field(default=None, description="For reminder jobs")

    result: str | None = Field(
        default=None, sa_column=Column(TEXT), description="JSON result"
    )
    error: str | None = Field(
        default=None, sa_column=Column(TEXT), description="Error message"
    )
    error_traceback: str | None = Field(
        default=None, sa_column=Column(TEXT), description="Full traceback"
    )
