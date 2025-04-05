from datetime import datetime
from typing import Dict

from pydantic import BaseModel, Field

from shared_models.queue import QueueMessage, QueueMessageSource, QueueMessageType


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


class CronMessage(QueueMessage):
    """Message from cron service."""

    type: QueueMessageType = QueueMessageType.TOOL
    source: QueueMessageSource = QueueMessageSource.CRON
    tool_name: str = "cron"
