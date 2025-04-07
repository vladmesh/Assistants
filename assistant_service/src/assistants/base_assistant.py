from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseAssistant(ABC):
    """Defines the common interface for all assistant implementations."""

    def __init__(
        self,
        assistant_id: str,
        name: str,
        config: Dict,
        tools: List,
        llm_config: Dict,
        **kwargs
    ):
        self.assistant_id = assistant_id
        self.name = name
        self.config = config  # General assistant config
        self.tools = tools  # List of available tool configurations from DB (or initialized tool instances)
        self.llm_config = llm_config  # LLM specific config (model name, api keys etc)
        # Store kwargs if they contain useful info like 'role', 'is_secretary', 'instructions' etc.
        self.additional_params = kwargs
        # Potentially extract common kwargs like instructions here
        self.instructions: Optional[str] = kwargs.get("instructions")

    @abstractmethod
    async def process_message(
        self, message_input: Any, user_id: str, thread_id: str, invoke_config: Dict
    ) -> Any:
        """Processes an incoming message and returns the assistant's response."""
        pass

    # Optional: Add common methods like close if needed
    # async def close(self):
    #     pass
