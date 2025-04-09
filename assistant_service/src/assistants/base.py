"""Base assistant interface"""

from abc import ABC, abstractmethod
from typing import List, Optional

from langchain_core.messages import BaseMessage


class OLDBaseAssistant(ABC):
    # DEPRECATED

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
        self,
        message: Optional[BaseMessage],
        user_id: Optional[str] = None,
        triggered_event: Optional[dict] = None,
    ) -> str:
        """Process a message or a triggered event and return response

        Args:
            message: Input message to process. Can be None if triggered_event is provided.
            user_id: Optional user identifier for tool context
            triggered_event: Optional dictionary containing data from an external trigger (e.g., reminder).

        Returns:
            Assistant's response
        """
