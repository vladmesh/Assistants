from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from langchain_core.messages import BaseMessage as LangBaseMessage
from langchain_core.messages import HumanMessage as LangHumanMessage
from langchain_core.messages import SystemMessage as LangSystemMessage
from langchain_core.messages import ToolMessage as LangToolMessage


class MessageSource(str, Enum):
    """Enum for message sources"""

    HUMAN = "human"
    SECRETARY = "secretary"
    TOOL = "tool"
    SYSTEM = "system"


class BaseMessage(LangBaseMessage):
    """Base class for all messages with timestamp and metadata."""

    def __init__(
        self,
        content: str,
        metadata: dict = None,
        source: MessageSource = MessageSource.SYSTEM,
    ):
        """Initialize message with content and metadata."""
        super().__init__(content=content)
        self._timestamp = datetime.now(timezone.utc)
        self._source = source
        self.metadata = metadata or {}

        # Move all metadata into additional_kwargs of base class
        self.additional_kwargs.update(
            {
                "timestamp": self._timestamp,
                "source": self._source,
                "metadata": self.metadata,
            }
        )

    @property
    def timestamp(self) -> datetime:
        """Get message timestamp"""
        return self._timestamp

    @property
    def source(self) -> MessageSource:
        """Get message source"""
        return self._source

    @property
    def type(self) -> str:
        """Get message type for LangChain compatibility"""
        return "base"

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary format"""
        return {
            "content": self.content,
            "source": self._source,
            "timestamp": self._timestamp.isoformat(),
            "metadata": self.metadata,
            "type": self.type,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseMessage":
        """Create message from dictionary format

        Args:
            data: Dictionary with message data

        Returns:
            New message instance
        """
        return cls(content=data["content"], metadata=data.get("metadata", {}))

    def __str__(self) -> str:
        """Format message in a way that LLM can understand

        Format: [SOURCE] (TIMESTAMP) CONTENT
        Example: [HUMAN] (2024-03-20T10:30:00Z) Hello, how are you?
        """
        timestamp = self._timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
        return f"[{self._source.name}] ({timestamp}) {self.content}"


class HumanMessage(BaseMessage, LangHumanMessage):
    """Human message with timestamp and metadata."""

    def __init__(self, content: str, metadata: dict = None):
        """Initialize human message."""
        super().__init__(content=content, metadata=metadata)
        self._source = MessageSource.HUMAN
        self.additional_kwargs["source"] = self._source

    @property
    def type(self) -> str:
        return "human"


class SecretaryMessage(BaseMessage):
    """Message from secretary assistant"""

    def __init__(self, content: str, metadata: dict = None):
        """Initialize secretary message."""
        super().__init__(content=content, metadata=metadata)
        self._source = MessageSource.SECRETARY
        self.additional_kwargs["source"] = self._source

    @property
    def type(self) -> str:
        return "secretary"


class ToolMessage(LangToolMessage):
    """Tool message with timestamp and metadata."""

    def __init__(
        self, content: str, tool_call_id: str, tool_name: str, metadata: dict = None
    ):
        """Initialize tool message."""
        # Initialize LangToolMessage with required parameters
        super().__init__(content=content, tool_call_id=tool_call_id)

        # Add our own functionality from BaseMessage
        self._timestamp = datetime.now(timezone.utc)
        self._source = MessageSource.TOOL
        self._tool_name = tool_name
        self.metadata = metadata or {}

    @property
    def type(self) -> str:
        return "tool"

    @property
    def timestamp(self) -> datetime:
        """Get message timestamp"""
        return self._timestamp

    @property
    def source(self) -> MessageSource:
        """Get message source"""
        return self._source

    @property
    def tool_name(self) -> str:
        """Get tool name"""
        return self._tool_name

    def __str__(self) -> str:
        """Return string representation of the message."""
        return f"[{self.source}:{self.tool_name}] ({self._timestamp.isoformat()}) {self.content}"


class SystemMessage(BaseMessage, LangSystemMessage):
    """System message with timestamp and metadata."""

    def __init__(self, content: str, metadata: dict = None):
        """Initialize system message."""
        super().__init__(content=content, metadata=metadata)
        self._source = MessageSource.SYSTEM
        self.additional_kwargs["source"] = self._source

    @property
    def type(self) -> str:
        return "system"


class MessagesThread:
    """Thread for storing conversation"""

    def __init__(self, thread_id: str):
        self.thread_id = thread_id
        self.messages: List[BaseMessage] = []
        self.created_at: datetime = datetime.now(timezone.utc)
        self.updated_at: datetime = self.created_at

    def add_message(self, message: BaseMessage):
        """Add a new message to the thread"""
        self.messages.append(message)
        self.updated_at = datetime.now(timezone.utc)

    def get_messages(self) -> List[BaseMessage]:
        """Get all messages in the thread"""
        return self.messages
