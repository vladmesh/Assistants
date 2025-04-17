import json
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import field_validator

# Need enums from models, adjust path if needed
# Assuming enums are accessible via models package (installed dependency)
# If models are also in shared_models, adjust import like: from ..models.reminder import ...
# from models.reminder import ReminderStatus, ReminderType
from ..enums import ReminderStatus, ReminderType  # Import from shared_models.enums
from .base import BaseSchema, TimestampSchema


class ReminderBase(BaseSchema):
    user_id: int
    assistant_id: UUID
    type: ReminderType
    trigger_at: Optional[datetime] = None
    cron_expression: Optional[str] = None
    payload: dict  # Store payload as dict for easier handling
    status: ReminderStatus = ReminderStatus.ACTIVE

    @field_validator("payload", mode="before")
    @classmethod
    def parse_payload(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("payload must be a valid JSON string")
        elif isinstance(v, dict):
            return v
        raise TypeError("payload must be a dict or a valid JSON string")


class ReminderCreate(ReminderBase):
    pass


class ReminderUpdate(BaseSchema):  # Allow partial updates
    status: Optional[ReminderStatus] = None
    # Add other fields if they should be updatable


class ReminderRead(ReminderBase, TimestampSchema):
    id: UUID
    created_by_assistant_id: UUID
    last_triggered_at: Optional[datetime] = None
