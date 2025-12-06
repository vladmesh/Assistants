import json
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import field_validator

# Import enums from shared_models
from shared_models.enums import ReminderStatus, ReminderType
from sqlalchemy import Column, String
from sqlmodel import Field, Relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .assistant import Assistant
    from .user import TelegramUser


class Reminder(BaseModel, table=True):
    """Модель напоминания"""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: int = Field(foreign_key="telegramuser.id", index=True)
    assistant_id: UUID = Field(foreign_key="assistant.id", index=True)
    type: ReminderType = Field(sa_column=Column(String, nullable=False))
    trigger_at: datetime | None = Field(default=None, index=True)  # для одноразовых
    cron_expression: str | None = Field(default=None)  # для периодических
    payload: str  # JSON строка с валидацией
    status: ReminderStatus = Field(
        sa_column=Column(String, default=ReminderStatus.ACTIVE.value),
    )
    last_triggered_at: datetime | None = Field(default=None)  # для повторяющихся

    # Relationships
    user: "TelegramUser" = Relationship(back_populates="reminders")  # noqa: F821
    assistant: "Assistant" = Relationship(
        back_populates="reminders",
        sa_relationship_kwargs={"foreign_keys": "Reminder.assistant_id"},
    )  # noqa: F821

    @field_validator("type")
    def validate_type(cls, v):
        if v not in [ReminderType.ONE_TIME.value, ReminderType.RECURRING.value]:
            raise ValueError(
                f"type должен быть '{ReminderType.ONE_TIME.value}' или "
                f"'{ReminderType.RECURRING.value}'"
            )
        return v

    @field_validator("status")
    def validate_status(cls, v):
        if v not in [
            ReminderStatus.ACTIVE.value,
            ReminderStatus.PAUSED.value,
            ReminderStatus.COMPLETED.value,
            ReminderStatus.CANCELLED.value,
        ]:
            valid_statuses = ", ".join(
                [s.value for s in ReminderStatus if s != ReminderStatus.PENDING]
            )
            raise ValueError(f"status должен быть одним из: {valid_statuses}")
        return v

    @field_validator("payload")
    def validate_payload(cls, v):
        try:
            json.loads(v)
            return v
        except json.JSONDecodeError as exc:
            raise ValueError("payload должен быть валидной JSON строкой") from exc

    class Config:
        table_name = "reminders"


__all__ = ["Reminder", "ReminderType", "ReminderStatus"]
