import json
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class QueueMessageType(str, Enum):
    """Type of queue message."""

    TOOL = "tool"
    HUMAN = "human"


class QueueMessageSource(str, Enum):
    """Defines the source of a message or trigger."""

    TELEGRAM = "telegram"
    CRON = "cron"
    API = "api"
    CALENDAR = "calendar"
    USER = "user"


class QueueMessageContent(BaseModel):
    """Content payload for queue messages."""

    message: str
    metadata: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.message


class QueueMessage(BaseModel):
    """Message sent TO assistant service."""

    type: QueueMessageType = QueueMessageType.HUMAN
    user_id: int
    source: QueueMessageSource = QueueMessageSource.USER
    content: QueueMessageContent | str
    metadata: dict[str, Any] | None = None
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC).replace(microsecond=0)
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_content(cls, values: dict[str, Any]) -> dict[str, Any]:
        content = values.get("content")
        if isinstance(content, dict):
            values["content"] = QueueMessageContent(**content)
        return values

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QueueMessage":
        """Deserialize from dict."""
        return cls(**data)


class ToolQueueMessage(QueueMessage):
    """Message produced by a tool."""

    tool_name: str
    type: QueueMessageType = QueueMessageType.TOOL

    @model_validator(mode="before")
    @classmethod
    def _ensure_type(cls, values: dict[str, Any]) -> dict[str, Any]:
        values.setdefault("type", QueueMessageType.TOOL)
        return values


class HumanQueueMessage(QueueMessage):
    """Message coming from a human user."""

    chat_id: int
    type: QueueMessageType = QueueMessageType.HUMAN

    @model_validator(mode="before")
    @classmethod
    def _ensure_type(cls, values: dict[str, Any]) -> dict[str, Any]:
        values.setdefault("type", QueueMessageType.HUMAN)
        return values


# --- Trigger Types and Model ---


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
    payload: dict[str, Any] = Field(
        default_factory=dict
    )  # Specific data associated with the trigger
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC).replace(microsecond=0)
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
# ... (Example Usage remains the same)


# --- Model for Assistant Responses ---


class AssistantResponseMessage(BaseModel):
    """
    Model for messages sent from the assistant service to other services via the queue.
    """

    user_id: int  # Internal user ID (from rest_service DB)
    status: str = "success"  # "success" or "error"
    source: str | None = None  # e.g., "assistant", "tool:reminder_tool"
    response: str | None = None  # Text response content if status is "success"
    error: str | None = None  # Error message content if status is "error"

    @model_validator(mode="before")
    def check_status_and_content(cls, values):
        """Ensure response is set on success and error on error."""
        status = values.get("status")
        response = values.get("response")
        error = values.get("error")

        if status == "success" and response is None:
            # Allow empty successful responses
            pass
        elif status == "error" and error is None:
            raise ValueError("Field 'error' is required when status is 'error'")
        elif status not in ["success", "error"]:
            raise ValueError("Field 'status' must be either 'success' or 'error'")

        return values

    model_config = {
        "extra": "forbid",  # Prevent unexpected fields during validation
    }
