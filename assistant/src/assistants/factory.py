from typing import List, Optional
from .base import BaseAssistant
from .openai_assistant import OpenAIAssistant
from .secretary import SecretaryLLMChat
from .sub_assistant import SubAssistantLLMChat
from tools.base import BaseTool
from config.settings import Settings
from langchain_openai import ChatOpenAI

class AssistantFactory:
    @staticmethod
    def create_main_assistant(
        settings: Settings,
        tools: Optional[List[BaseTool]] = None
    ) -> BaseAssistant:
        """Create main assistant based on settings."""
        if settings.MAIN_ASSISTANT_TYPE == "openai":
            return OpenAIAssistant(
                name="secretary",
                instructions=settings.MAIN_ASSISTANT_INSTRUCTIONS,
                model=settings.MAIN_ASSISTANT_MODEL,
                tools=[tool.openai_schema for tool in (tools or [])],
                tool_instances=tools or []
            )
        elif settings.MAIN_ASSISTANT_TYPE == "llm":
            return SecretaryLLMChat(
                name="secretary",
                instructions=settings.MAIN_ASSISTANT_INSTRUCTIONS,
                llm=ChatOpenAI(model=settings.MAIN_ASSISTANT_MODEL),
                tools=tools or []
            )
        else:
            raise ValueError(f"Unknown assistant type: {settings.MAIN_ASSISTANT_TYPE}")
    
    @staticmethod
    def create_sub_assistant(
        settings: Settings,
        tools: Optional[List[BaseTool]] = None
    ) -> BaseAssistant:
        """Create sub-assistant based on settings."""
        if settings.SUB_ASSISTANT_TYPE == "openai":
            return OpenAIAssistant(
                name="writer_assistant",
                instructions=settings.SUB_ASSISTANT_INSTRUCTIONS,
                model=settings.SUB_ASSISTANT_MODEL,
                tools=[tool.openai_schema for tool in (tools or [])],
                tool_instances=tools or []
            )
        elif settings.SUB_ASSISTANT_TYPE == "llm":
            return SubAssistantLLMChat(
                name="writer_assistant",
                instructions=settings.SUB_ASSISTANT_INSTRUCTIONS,
                llm=ChatOpenAI(model=settings.SUB_ASSISTANT_MODEL),
                tools=tools or []
            )
        else:
            raise ValueError(f"Unknown assistant type: {settings.SUB_ASSISTANT_TYPE}") 