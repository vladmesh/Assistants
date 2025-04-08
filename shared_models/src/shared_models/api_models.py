import enum
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator


# Enums (copied from rest_service models)
class ReminderType(str, enum.Enum):
    ONE_TIME = "one_time"
    RECURRING = "recurring"


class ReminderStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# Pydantic Models (adapted from rest_service models/schemas)


class ToolModel(BaseModel):
    """Pydantic model for Tool (API contract)"""

    id: UUID
    name: str
    tool_type: str  # Using str for simplicity, could use ToolType enum if defined here
    description: str
    input_schema: Optional[str] = None
    assistant_id: Optional[UUID] = None  # For sub_assistant type
    is_active: bool
    created_at: Optional[
        datetime
    ] = None  # Added from Tool definition in rest_service/models/assistant.py, assuming it might be returned
    updated_at: Optional[datetime] = None  # Added from Tool definition

    @validator("input_schema")
    def validate_input_schema(cls, v):
        if v is not None:
            try:
                json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("input_schema must be a valid JSON string or null")
        return v

    @property
    def input_schema_dict(self) -> Optional[Dict[str, Any]]:
        """Get input schema as dictionary"""
        if self.input_schema:
            try:
                return json.loads(self.input_schema)
            except json.JSONDecodeError:
                return None  # Or raise an error, depending on desired strictness
        return None


class AssistantModel(BaseModel):
    """Pydantic model for Assistant (API contract)"""

    id: UUID
    name: str
    is_secretary: bool
    model: str
    instructions: str
    assistant_type: str  # Could use AssistantType enum if defined here
    openai_assistant_id: Optional[str] = None
    is_active: bool
    updated_at: Optional[datetime] = None
    # Note: We fetch tools separately, so 'tools' field is removed from here


class UserModel(BaseModel):
    """Pydantic model for User (API contract)"""

    id: int  # Database ID
    telegram_id: int
    username: Optional[str] = None


class ReminderModel(BaseModel):
    """Pydantic model for Reminder (API contract)"""

    id: UUID
    user_id: int
    assistant_id: UUID
    created_by_assistant_id: UUID
    type: ReminderType
    trigger_at: Optional[datetime] = None
    cron_expression: Optional[str] = None
    payload: str
    status: ReminderStatus
    last_triggered_at: Optional[datetime] = None
    created_at: Optional[datetime] = None  # Added from BaseModel in rest_service
    updated_at: Optional[datetime] = None  # Added from BaseModel in rest_service

    @validator("payload")
    def validate_payload(cls, v):
        try:
            json.loads(v)
            return v
        except json.JSONDecodeError:
            raise ValueError("payload must be a valid JSON string")


class CreateReminderRequest(BaseModel):
    """Pydantic model for creating a Reminder (API contract)"""

    user_id: int
    assistant_id: UUID
    type: ReminderType
    trigger_at: Optional[datetime] = None
    cron_expression: Optional[str] = None
    payload: str
    status: ReminderStatus = ReminderStatus.ACTIVE

    @validator("payload")
    def validate_payload(cls, v):
        try:
            json.loads(v)
            return v
        except json.JSONDecodeError:
            raise ValueError("payload must be a valid JSON string")


class UserSecretaryAssignment(BaseModel):
    """Pydantic model for User-Secretary assignment (API contract)"""

    user_id: int
    secretary_id: UUID
    updated_at: datetime  # Timestamp of the UserSecretaryLink update
