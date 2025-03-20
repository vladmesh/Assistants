from typing import List, Optional
from .base import BaseAssistant
from .openai_assistant import OpenAIAssistant
from .secretary import SecretaryLLMChat
from .sub_assistant import SubAssistantLLMChat
from tools.base import BaseTool
from config.settings import Settings
from langchain_openai import ChatOpenAI
from services.rest_service import RestServiceClient
from config.logger import get_logger

logger = get_logger(__name__)

class AssistantFactory:
    def __init__(self, settings: Settings):
        """Initialize the factory with settings and REST client"""
        self.settings = settings
        self.rest_client = RestServiceClient()
    
    async def close(self):
        """Close REST client connection"""
        await self.rest_client.close()
    
    async def create_main_assistant(
        self,
        tools: Optional[List[BaseTool]] = None
    ) -> BaseAssistant:
        """Create main assistant based on settings."""
        # Get secretary assistant from REST service
        assistants = await self.rest_client.get_assistants()
        secretary = next((a for a in assistants if a.is_secretary), None)
        if not secretary:
            raise ValueError("Secretary assistant not found")
        
        # Log tools before creating assistant
        if tools:
            logger.info("Creating assistant with tools", 
                       tool_count=len(tools),
                       tool_names=[tool.name for tool in tools])
        
        if secretary.assistant_type == "openai_api":
            return OpenAIAssistant(
                assistant_id=secretary.openai_assistant_id,
                name=secretary.name,
                instructions=secretary.instructions,
                model=secretary.model,
                tools=[tool.openai_schema for tool in (tools or [])],
                tool_instances=tools or []
            )
        elif secretary.assistant_type == "llm":
            return SecretaryLLMChat(
                llm=ChatOpenAI(model=secretary.model),
                name=secretary.name,
                instructions=secretary.instructions,
                tools=tools or []
            )
        else:
            raise ValueError(f"Unknown assistant type: {secretary.assistant_type}")
    
    async def create_sub_assistant(
        self,
        assistant_data: dict,
        tools: Optional[List[BaseTool]] = None
    ) -> BaseAssistant:
        """Create sub-assistant based on assistant data.
        
        Args:
            assistant_data: Assistant data from REST service
            tools: Optional list of tools for the assistant
        """
        if assistant_data.assistant_type == "openai_api":
            return OpenAIAssistant(
                assistant_id=assistant_data.openai_assistant_id,
                name=assistant_data.name,
                instructions=assistant_data.instructions,
                model=assistant_data.model,
                tools=[tool.openai_schema for tool in (tools or [])],
                tool_instances=tools or []
            )
        elif assistant_data.assistant_type == "llm":
            return SubAssistantLLMChat(
                llm=ChatOpenAI(model=assistant_data.model),
                name=assistant_data.name,
                instructions=assistant_data.instructions,
                tools=tools or []
            )
        else:
            raise ValueError(f"Unknown assistant type: {assistant_data.assistant_type}") 