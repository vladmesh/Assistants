from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, Field


class MessageContent(BaseModel):
    """Content of the message with metadata."""

    message: str
    metadata: Dict = Field(default_factory=dict)


class QueueMessage(BaseModel):
    """Standardized message format for queue communication."""

    type: str = "tool_message"
    user_id: int
    source: str = "cron"
    content: MessageContent
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
