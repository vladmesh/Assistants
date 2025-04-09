from abc import ABC, abstractmethod
from typing import Dict, List, Optional

# Import BaseMessage for type hinting
from langchain_core.messages import BaseMessage


class BaseAssistant(ABC):
    """Defines the minimal common interface for all assistant implementations."""

    def __init__(
        self,
        assistant_id: str,
        name: str,
        config: Dict,
        tool_definitions: List[Dict],
        **kwargs
    ):
        """Initializes the assistant with basic info and raw configurations.

        Args:
            assistant_id: Unique identifier for the assistant instance.
            name: Name of the assistant.
            config: Dictionary containing all configuration parameters from the database
                    (e.g., model, instructions, llm settings, is_secretary).
                    Specific implementations are responsible for parsing this.
            tool_definitions: List of dictionaries, each representing the raw tool
                              definition from the database.
                              Specific implementations handle tool initialization.
            **kwargs: Additional keyword arguments for future flexibility.
        """
        self.assistant_id = assistant_id
        self.name = name
        self.config = config
        self.tool_definitions = tool_definitions
        self.kwargs = kwargs

    @abstractmethod
    async def process_message(
        self,
        message: Optional[BaseMessage],
        user_id: str,
        triggered_event: Optional[dict] = None,
    ) -> str:
        """Processes an incoming message or a triggered event and returns the assistant's response string.

        Args:
            message: The input message (standard Langchain BaseMessage).
                     Can be None if triggered_event is provided.
            user_id: The identifier of the user initiating the request.
                     The assistant implementation is responsible for managing
                     conversation context/memory based on the user_id.
            triggered_event: Optional dictionary containing data from an external trigger (e.g., reminder).

        Returns:
            A string containing the assistant's response.
        """

    # Optional: Add other common abstract methods if needed in the future
    # e.g., async def close(self): pass
