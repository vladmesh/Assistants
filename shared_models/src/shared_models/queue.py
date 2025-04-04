from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class QueueMessageType(str, Enum):
    """Types of messages in queue"""

    TOOL = "tool_message"
    HUMAN = "human_message"


class QueueMessageSource(str, Enum):
    """Sources of messages in queue"""

    CRON = "cron"
    CALENDAR = "calendar"
    USER = "user"


class QueueMessageContent(BaseModel):
    """Content of queue message"""

    message: str = Field(..., description="Message text")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional data"
    )


class QueueMessage(BaseModel):
    """Base class for all queue messages"""

    type: QueueMessageType = Field(..., description="Message type")
    user_id: int = Field(..., description="User ID in database")
    source: QueueMessageSource = Field(..., description="Message source")
    content: QueueMessageContent = Field(..., description="Message content")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(), description="Message creation time"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary"""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QueueMessage":
        """Create message from dictionary"""
        return cls(**data)


class ToolQueueMessage(QueueMessage):
    """Message from tool"""

    type: QueueMessageType = Field(
        default=QueueMessageType.TOOL, description="Message type"
    )
    tool_name: str = Field(..., description="Tool name")


class HumanQueueMessage(QueueMessage):
    """Message from user"""

    type: QueueMessageType = Field(
        default=QueueMessageType.HUMAN, description="Message type"
    )
    chat_id: Optional[int] = Field(None, description="Telegram chat ID")
