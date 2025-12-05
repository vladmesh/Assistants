import json
from datetime import datetime
from uuid import UUID

from pydantic import field_validator

# Enums live in shared_models.enums; adjust if models are packaged separately
# from models.reminder import ReminderStatus, ReminderType
from ..enums import ReminderStatus, ReminderType
from .base import BaseSchema, TimestampSchema


class ReminderBase(BaseSchema):
    user_id: int
    assistant_id: UUID
    type: ReminderType
    trigger_at: datetime | None = None
    cron_expression: str | None = None
    payload: dict  # Store payload as dict for easier handling
    status: ReminderStatus = ReminderStatus.ACTIVE

    @field_validator("payload", mode="before")
    @classmethod
    def parse_payload(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError as err:
                raise ValueError("payload must be a valid JSON string") from err
        elif isinstance(v, dict):
            return v
        raise TypeError("payload must be a dict or a valid JSON string")


class ReminderCreate(ReminderBase):
    pass


class ReminderUpdate(BaseSchema):  # Allow partial updates
    status: ReminderStatus | None = None
    # Add other fields if they should be updatable


class ReminderRead(ReminderBase, TimestampSchema):
    id: UUID
    last_triggered_at: datetime | None = None
