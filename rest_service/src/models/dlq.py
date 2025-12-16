"""Dead Letter Queue (DLQ) models."""

from datetime import datetime

from pydantic import BaseModel


class DLQMessageResponse(BaseModel):
    """DLQ message response."""

    message_id: str
    original_message_id: str
    payload: str
    error_type: str
    error_message: str
    retry_count: int
    failed_at: datetime
    user_id: str | None


class DLQStatsResponse(BaseModel):
    """DLQ statistics."""

    queue_name: str
    total_messages: int
    by_error_type: dict[str, int]
    oldest_message_at: datetime | None
    newest_message_at: datetime | None
