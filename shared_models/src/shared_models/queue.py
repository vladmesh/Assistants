import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class QueueMessageSource(str, Enum):
    TELEGRAM = "telegram"
    CRON = "cron"
    API = "api"
    CALENDAR = "calendar"


class QueueMessageType(str, Enum):
    HUMAN = "human"
    TOOL = "tool"


class BaseQueueMessageContent(BaseModel):
    message: str
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class HumanQueueMessageContent(BaseQueueMessageContent):
    pass


class ToolQueueMessageContent(BaseQueueMessageContent):
    @model_validator(mode="before")
    def ensure_tool_name_in_metadata(cls, values):
        """Validate that metadata contains 'tool_name'."""
        metadata = values.get("metadata")
        if not metadata or "tool_name" not in metadata:
            raise ValueError("'tool_name' is required in metadata for ToolQueueMessage")
        return values

    @field_validator("metadata")
    def validate_tool_name_type(cls, v):
        """Ensure tool_name is a string if present."""
        if "tool_name" in v and not isinstance(v["tool_name"], str):
            raise ValueError("'tool_name' must be a string")
        return v


class QueueMessage(BaseModel):
    user_id: int
    source: QueueMessageSource
    type: QueueMessageType
    content: HumanQueueMessageContent | ToolQueueMessageContent
    timestamp: datetime = Field(default_factory=datetime.now)

    @model_validator(mode="before")
    def check_content_type(cls, values):
        """Ensure content matches message type."""
        content_data = values.get("content")
        message_type = values.get("type")

        if message_type == QueueMessageType.HUMAN:
            # For HUMAN, allow simple string content, auto-convert
            if isinstance(content_data, str):
                values["content"] = HumanQueueMessageContent(message=content_data)
            elif isinstance(content_data, dict):
                values["content"] = HumanQueueMessageContent(**content_data)
            elif not isinstance(content_data, HumanQueueMessageContent):
                raise ValueError(
                    "Content must be HumanQueueMessageContent or str for HUMAN type"
                )
        elif message_type == QueueMessageType.TOOL:
            if isinstance(content_data, dict):
                # Validate ToolQueueMessageContent structure explicitly
                try:
                    values["content"] = ToolQueueMessageContent(**content_data)
                except ValueError as e:
                    raise ValueError(f"Invalid content for TOOL type: {e}")
            elif not isinstance(content_data, ToolQueueMessageContent):
                raise ValueError(
                    "Content must be ToolQueueMessageContent or dict for TOOL type"
                )
        else:
            # This case should ideally not be reached if type is validated first
            raise ValueError(f"Unsupported message type: {message_type}")

        return values

    @classmethod
    def from_string(cls, json_string: str) -> "QueueMessage":
        """Deserialize from JSON string."""
        return cls(**json.loads(json_string))


# --- New Trigger Types and Model ---
from datetime import datetime, timezone


class TriggerType(str, Enum):
    """Defines the types of system-generated triggers."""

    REMINDER = "reminder_triggered"
    GOOGLE_AUTH = "google_auth_successful"
    # Add more trigger types as needed in the future


class QueueTrigger(BaseModel):
    """Model for system-generated trigger events sent via the queue."""

    trigger_type: TriggerType  # Identifies the specific trigger event
    user_id: int  # The user this trigger pertains to
    source: QueueMessageSource  # The service that originated the trigger
    payload: Dict[str, Any] = Field(
        default_factory=dict
    )  # Specific data associated with the trigger
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )  # Timestamp of trigger generation

    model_config = {
        "frozen": True,  # Make trigger objects immutable after creation
        "extra": "forbid",  # Prevent unexpected fields
    }

    def to_json(self) -> str:
        """Serialize the trigger object to a JSON string."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, json_string: str) -> "QueueTrigger":
        """Deserialize a QueueTrigger from a JSON string."""
        data = json.loads(json_string)
        return cls(**data)


# Example Usage (for illustration, not part of the actual file)
# reminder_trigger = QueueTrigger(
#     trigger_type=TriggerType.REMINDER,
#     user_id=123,
#     source=QueueMessageSource.CRON,
#     payload={"reminder_id": "abc", "message": "Time for your meeting!"},
# )
# auth_trigger = QueueTrigger(
#     trigger_type=TriggerType.GOOGLE_AUTH,
#     user_id=456,
#     source=QueueMessageSource.CALENDAR,
#     payload={"scopes_granted": ["calendar.readonly"]},
# )
#
# print(reminder_trigger.to_json())
# print(QueueTrigger.from_json(auth_trigger.to_json()))
