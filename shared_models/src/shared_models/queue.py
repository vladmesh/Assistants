import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


class QueueMessageSource(str, Enum):
    """Defines the source of a message or trigger."""

    TELEGRAM = "telegram"
    CRON = "cron"
    API = "api"
    CALENDAR = "calendar"


class QueueMessage(BaseModel):
    """Model for messages sent TO the assistant service, specifically for user input."""

    user_id: int
    content: str  # Changed from Union type to simple string
    metadata: Optional[Dict[str, Any]] = None  # Added optional metadata field
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def from_string(cls, json_string: str) -> "QueueMessage":
        """Deserialize from JSON string."""
        return cls(**json.loads(json_string))


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
# ... (Example Usage remains the same)


# --- Model for Assistant Responses ---


class AssistantResponseMessage(BaseModel):
    """
    Model for messages sent FROM the assistant service TO other services (e.g., Telegram bot) via the queue.
    """

    user_id: int  # Internal user ID (from rest_service DB)
    status: str = "success"  # "success" or "error"
    source: Optional[str] = None  # e.g., "assistant", "tool:reminder_tool"
    response: Optional[str] = None  # Text response content if status is "success"
    error: Optional[str] = None  # Error message content if status is "error"

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
