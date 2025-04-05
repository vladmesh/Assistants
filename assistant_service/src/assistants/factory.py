from typing import Dict, List, Optional

from config.logger import get_logger
from config.settings import Settings
from langchain_openai import ChatOpenAI
from services.rest_service import RestServiceClient
from tools.base import BaseTool
from tools.rest_service_tool import RestServiceTool

from .base import BaseAssistant
from .llm_chat import BaseLLMChat
from .openai_assistant import OpenAIAssistant

logger = get_logger(__name__)


class AssistantFactory:
    def __init__(self, settings: Settings):
        """Initialize the factory with settings and REST client"""
        self.settings = settings
        self.rest_client = RestServiceClient()
        self._secretary_cache: Dict[int, BaseAssistant] = {}

    async def close(self):
        """Close REST client connection and all assistant instances"""
        await self.rest_client.close()

        # Close all assistant instances
        for assistant in self._secretary_cache.values():
            if hasattr(assistant, "close"):
                await assistant.close()

        self._secretary_cache.clear()

    async def get_user_secretary(self, user_id: int) -> BaseAssistant:
        """Get or create secretary assistant for user.

        Args:
            user_id: Telegram user ID

        Returns:
            Secretary assistant instance

        Raises:
            ValueError: If secretary not found for user
        """
        # Check cache first
        if user_id in self._secretary_cache:
            return self._secretary_cache[user_id]

        # Get user's secretary from REST service
        try:
            secretary = await self.rest_client.get_user_secretary(user_id)
        except Exception as e:
            logger.error("Failed to get user secretary", user_id=user_id, error=str(e))
            # If no secretary found, get default secretary
            secretary = await self.get_secretary_assistant()

        # Initialize tools
        tools = await self.initialize_tools(str(secretary.id))

        # Create assistant instance
        if secretary.assistant_type == "openai_api":
            assistant = OpenAIAssistant(
                assistant_id=secretary.openai_assistant_id,
                name=secretary.name,
                instructions=secretary.instructions,
                model=secretary.model,
                tools=[tool.openai_schema for tool in tools],
                tool_instances=tools,
            )
        elif secretary.assistant_type == "llm":
            assistant = BaseLLMChat(
                llm=ChatOpenAI(model=secretary.model),
                name=secretary.name,
                instructions=secretary.instructions,
                tools=tools,
                is_secretary=True,
                assistant_id=str(secretary.id),
            )
        else:
            raise ValueError(f"Unknown assistant type: {secretary.assistant_type}")

        # Cache assistant
        self._secretary_cache[user_id] = assistant

        return assistant

    async def get_secretary_assistant(self) -> dict:
        """Get secretary assistant from REST service.

        Returns:
            Assistant data from REST service

        Raises:
            ValueError: If secretary assistant not found
        """
        assistants = await self.rest_client.get_assistants()
        secretary = next((a for a in assistants if a.is_secretary), None)
        if not secretary:
            raise ValueError("Secretary assistant not found")
        return secretary

    async def initialize_tools(self, secretary_id: str) -> List[BaseTool]:
        """Initialize tools for secretary assistant.

        Args:
            secretary_id: ID of the secretary assistant

        Returns:
            List of initialized tools
        """
        # Get tools for secretary
        logger.info("Getting tools for secretary", secretary_id=secretary_id)
        secretary_tools = await self.rest_client.get_assistant_tools(str(secretary_id))
        logger.info("Tools fetched", tool_count=len(secretary_tools))

        tools = []
        # Initialize tools based on their types
        for tool_data in secretary_tools:
            logger.info(
                "Initializing tool",
                tool_name=tool_data.name,
                tool_type=tool_data.tool_type,
                tool_id=tool_data.id,
                assistant_id=tool_data.assistant_id,
            )

            # Convert REST service tool data to RestServiceTool
            tool_dict = tool_data.dict()
            tool_dict["settings"] = self.settings
            logger.info("Tool data from REST service", tool_dict=tool_dict)
            rest_tool = RestServiceTool(**tool_dict)
            logger.info(
                "Created RestServiceTool",
                name=rest_tool.name,
                tool_type=rest_tool.tool_type,
                assistant_id=rest_tool.assistant_id,
            )

            # Convert to actual tool
            tool = rest_tool.to_tool()
            logger.info(
                "Converted to actual tool",
                name=tool.name,
                tool_type=getattr(tool, "tool_type", None),
                assistant_id=getattr(tool, "assistant_id", None),
            )

            # For sub_assistant type, get and set the sub-assistant
            if rest_tool.tool_type == "sub_assistant":
                logger.info(
                    "Creating sub_assistant tool",
                    assistant_id=rest_tool.assistant_id,
                    tool_name=tool.name,
                )
                sub_assistant = await self.rest_client.get_assistant(
                    rest_tool.assistant_id
                )
                logger.info(
                    "Got sub_assistant from REST service",
                    assistant_id=sub_assistant.id,
                    name=sub_assistant.name,
                    assistant_type=sub_assistant.assistant_type,
                )
                sub_assistant_instance = await self.create_sub_assistant(sub_assistant)
                logger.info(
                    "Created sub_assistant instance",
                    assistant_id=sub_assistant_instance.assistant_id,
                    name=sub_assistant_instance.name,
                    assistant_type=getattr(
                        sub_assistant_instance, "assistant_type", None
                    ),
                )
                tool.sub_assistant = sub_assistant_instance
                tool.assistant_id = rest_tool.assistant_id
                logger.info(
                    "Set sub_assistant in tool",
                    tool_assistant_id=tool.assistant_id,
                    tool_name=tool.name,
                    tool_type=getattr(tool, "tool_type", None),
                )

            tools.append(tool)
            logger.info("Added tool", name=tool.name)

        return tools

    async def create_main_assistant(self) -> BaseAssistant:
        """Create main assistant based on settings."""
        # Get secretary assistant from REST service
        secretary = await self.get_secretary_assistant()

        # Initialize tools
        tools = await self.initialize_tools(str(secretary.id))

        # Log tools before creating assistant
        if tools:
            logger.info(
                "Creating assistant with tools",
                tool_count=len(tools),
                tool_names=[tool.name for tool in tools],
            )

        if secretary.assistant_type == "openai_api":
            return OpenAIAssistant(
                assistant_id=secretary.openai_assistant_id,
                name=secretary.name,
                instructions=secretary.instructions,
                model=secretary.model,
                tools=[tool.openai_schema for tool in tools],
                tool_instances=tools,
            )
        elif secretary.assistant_type == "llm":
            return BaseLLMChat(
                llm=ChatOpenAI(model=secretary.model),
                name=secretary.name,
                instructions=secretary.instructions,
                tools=tools,
                is_secretary=True,
            )
        else:
            raise ValueError(f"Unknown assistant type: {secretary.assistant_type}")

    async def create_sub_assistant(
        self, assistant_data: dict, tools: Optional[List[BaseTool]] = None
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
                tool_instances=tools or [],
            )
        elif assistant_data.assistant_type == "llm":
            return BaseLLMChat(
                llm=ChatOpenAI(model=assistant_data.model),
                name=assistant_data.name,
                instructions=assistant_data.instructions,
                tools=tools or [],
                is_secretary=False,
            )
        else:
            raise ValueError(f"Unknown assistant type: {assistant_data.assistant_type}")
