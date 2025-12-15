"""QueueMessageLog model for tracking Redis queue messages."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import TEXT, Column
from sqlmodel import Field

from .base import BaseModel


class QueueDirection(str, Enum):
    INBOUND = "inbound"  # To assistant_service
    OUTBOUND = "outbound"  # From assistant_service


class QueueMessageLog(BaseModel, table=True):
    """Logs messages passing through Redis queues.

    Used for observability and debugging of message flow
    between services.
    """

    __tablename__ = "queue_message_logs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    queue_name: str = Field(
        index=True, description="Queue name: to_secretary, to_telegram"
    )
    direction: QueueDirection = Field(description="Message direction")

    correlation_id: str | None = Field(
        default=None, index=True, description="Request correlation ID"
    )
    user_id: int | None = Field(
        default=None, index=True, description="User ID if applicable"
    )

    message_type: str = Field(
        description="Message type: human, tool, trigger, response"
    )
    payload: str = Field(sa_column=Column(TEXT), description="JSON message payload")

    source: str | None = Field(
        default=None, description="Message source: telegram, cron, calendar"
    )
    processed: bool = Field(default=False, description="Whether message was processed")
    processed_at: datetime | None = Field(
        default=None, description="When message was processed"
    )
