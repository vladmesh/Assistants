"""Base assistant interface"""

from abc import ABC, abstractmethod
from typing import List, Optional

from langchain_core.messages import BaseMessage


class BaseAssistant(ABC):
    """Base class for all assistants"""

    def __init__(
        self,
        name: str,
        instructions: str,
        tools: Optional[List] = None,
        metadata: Optional[dict] = None,
    ):
        self.name = name
        self.instructions = instructions
        self.tools = tools or []
        self.metadata = metadata or {}

    def _set_tool_context(self, user_id: Optional[str] = None) -> None:
        """Set context for all tools before execution"""
        if not user_id:
            return

        for tool in self.tools:
            if hasattr(tool, "user_id"):
                tool.user_id = user_id

    @abstractmethod
    async def process_message(
        self, message: BaseMessage, user_id: Optional[str] = None
    ) -> str:
        """Process a message and return response

        Args:
            message: Input message to process
            user_id: Optional user identifier for tool context

        Returns:
            Assistant's response
        """
