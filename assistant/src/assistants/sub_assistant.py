"""Sub-assistant implementations"""
from typing import List, Optional
from abc import ABC

from langchain_core.messages import BaseMessage
from langchain_core.language_models import BaseLanguageModel

from assistants.base import BaseAssistant
from assistants.llm_chat import BaseLLMChat
from tools.base import BaseTool

class SubAssistant(BaseAssistant, ABC):
    """Assistant that gets messages only from Secretary and other SubAssistants. Never interacts with user"""
    pass

class SubAssistantLLMChat(SubAssistant, BaseLLMChat):
    """Implementation of sub-assistant using ReAct agent with LLM chat model"""
    
    def __init__(
            self,
            llm: BaseLanguageModel,
            system_message: Optional[str] = None,
            tools: Optional[List[BaseTool]] = None,
            name: str = "sub_assistant",
            instructions: str = "You are a helpful sub-assistant",
            assistant_id: Optional[str] = None
    ):
        BaseLLMChat.__init__(
            self,
            llm=llm,
            system_message=system_message,
            tools=tools,
            name=name,
            instructions=instructions
        )
        self.assistant_id = assistant_id 