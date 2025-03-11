"""Base LLM chat assistant implementation"""
from typing import List, Optional, Any
from abc import ABC

from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.language_models import BaseLanguageModel
from langgraph.prebuilt import create_react_agent

from assistants.base import BaseAssistant
from tools.base import BaseTool
from utils.error_handler import AssistantError, MessageProcessingError, handle_assistant_error

class BaseLLMChat(BaseAssistant, ABC):
    """Base class for LLM chat assistants"""
    
    def __init__(
            self,
            llm: BaseLanguageModel,
            system_message: Optional[str] = None,
            tools: Optional[List[BaseTool]] = None,
            name: str = "base_llm_chat",
            instructions: str = "You are a helpful assistant"
    ):
        try:
            super().__init__(name=name, instructions=instructions, tools=tools)
            self.llm = llm
            self.system_message = system_message or instructions
            self.agent = self._create_agent()
        except Exception as e:
            raise AssistantError(f"Failed to initialize assistant: {str(e)}", name)

    def _create_agent(self) -> Any:
        """Create the agent using LangGraph
        
        Raises:
            AssistantError: If agent creation fails
        """
        try:
            return create_react_agent(
                self.llm,
                self.tools,
                prompt = SystemMessage(content=self.system_message) if self.system_message else None
            )
        except Exception as e:
            raise AssistantError(f"Failed to create agent: {str(e)}", self.name)

    async def process_message(self, message: BaseMessage, user_id: Optional[str] = None) -> str:
        """Process a message using the agent
        
        Args:
            message: Input message to process
            user_id: Optional user identifier
            
        Returns:
            Assistant's response
            
        Raises:
            MessageProcessingError: If message processing fails
        """
        try:
            response = await self.agent.ainvoke({"messages": [message]})
            if not response:
                raise MessageProcessingError("Agent returned empty response", self.name)
            return response
        except Exception as e:
            error_msg = handle_assistant_error(e, self.name)
            return error_msg 