"""Secretary assistant implementations"""
from typing import List, Optional, Any
from abc import ABC, abstractmethod

from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.language_models import BaseLanguageModel
from langgraph.prebuilt import create_react_agent

from assistants.base import BaseAssistant
from assistants.llm_chat import BaseLLMChat
from tools.base import BaseTool

class Secretary(BaseAssistant, ABC):
    """Assistant, who get messages only from user. Can use other assistants as tool"""
    def __init__(
            self,
            llm: Optional[BaseLanguageModel] = None,
            tools: Optional[List[BaseTool]] = None,
            **kwargs
    ):
        self.llm = llm
        self.tools = tools or []
        self.agent = self._create_agent()

    @abstractmethod
    def _create_agent(self) -> Any:
        """Create the underlying agent implementation"""
        pass

    @abstractmethod
    async def process_message(self, message: BaseMessage, user_id: Optional[int] = None) -> BaseMessage:
        """Process a message in a given thread"""
        pass

class SecretaryLLMChat(Secretary, BaseLLMChat):
    """Implementation of secretary using ReAct agent with LLM chat model"""
    
    def __init__(
            self,
            llm: BaseLanguageModel,
            system_message: Optional[str] = None,
            tools: Optional[List[BaseTool]] = None,
            name: str = "secretary",
            instructions: str = "You are a helpful secretary assistant"
    ):
        BaseLLMChat.__init__(
            self,
            llm=llm,
            system_message=system_message,
            tools=tools,
            name=name,
            instructions=instructions
        )

    def _create_agent(self) -> Any:
        # Create the agent using LangGraph
        return create_react_agent(
            self.llm,
            self.tools,
            prompt = SystemMessage(content=self.system_message) if self.system_message else None
        )

    async def process_message(self, message: BaseMessage, user_id: Optional[str] = None) -> str:
        """Process a message using the agent"""
        response = await self.agent.ainvoke({"messages": [message]})
        return response or "Извините, я не смог обработать ваше сообщение" 