import json
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import validator

from .base import BaseSchema, TimestampSchema


class ReminderBase(BaseSchema):
    user_id: int
    assistant_id: UUID
    type: str
    trigger_at: Optional[datetime] = None
    cron_expression: Optional[str] = None
    payload: str
    status: str = "active"

    @validator("payload")
    def validate_payload(cls, v):
        try:
            # Проверяем, что строка является валидным JSON
            json.loads(v)
            return v
        except json.JSONDecodeError:
            raise ValueError("payload должен быть валидной JSON строкой")

    @validator("type")
    def validate_type(cls, v):
        if v not in ["one_time", "recurring"]:
            raise ValueError('type должен быть "one_time" или "recurring"')
        return v

    @validator("status")
    def validate_status(cls, v):
        if v not in ["active", "paused", "completed", "cancelled"]:
            raise ValueError(
                'status должен быть "active", "paused", "completed" или "cancelled"'
            )
        return v


class ReminderCreate(ReminderBase):
    pass


class ReminderUpdate(BaseSchema):
    status: Optional[str] = None

    @validator("status")
    def validate_status(cls, v):
        if v is not None and v not in [
            "active",
            "paused",
            "completed",
            "cancelled",
        ]:
            raise ValueError(
                'status должен быть "active", "paused", "completed" или "cancelled"'
            )
        return v


class ReminderRead(ReminderBase, TimestampSchema):
    id: UUID
    created_by_assistant_id: UUID
    last_triggered_at: Optional[datetime] = None
