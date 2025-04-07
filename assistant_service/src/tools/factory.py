# assistant_service/src/tools/factory.py
import logging
from typing import List, Optional, Type

from config.settings import Settings
from langchain_core.tools import Tool

# Import shared models
from tools.calendar_tool import CalendarCreateTool, CalendarListTool
from tools.reminder_tool import ReminderTool

# Import specific tool implementation classes
from tools.time_tool import TimeToolWrapper
from tools.web_search_tool import WebSearchTool

from shared_models import ToolModel

# Import other tools as needed
# from tools.rest_service_tool import RestServiceTool # Example if needed


logger = logging.getLogger(__name__)


class ToolFactory:
    """Factory class for creating tool instances from definitions."""

    def __init__(self, settings: Settings):
        """Initializes the factory with necessary settings."""
        self.settings = settings
        # Client is now initialized within tools lazily or passed via BaseTool kwargs
        # self.rest_client = RestServiceClient()

    def create_langchain_tools(
        self, tool_definitions: List[ToolModel], user_id: str, assistant_id: str
    ) -> List[Tool]:
        """
        Creates Langchain Tool instances from a list of ToolModel definitions.
        Name and Description are now fetched from tool_definitions.
        Args_schema is defined in the tool class.
        """
        tools = []
        for tool_def in tool_definitions:
            logger.debug(
                f"Processing tool definition: {tool_def.name} (Type: {tool_def.tool_type})"
            )

            tool_type = tool_def.tool_type
            tool_name = tool_def.name  # Get name from DB model
            tool_description = tool_def.description  # Get description from DB model
            tool_id_str = str(tool_def.id)
            # sub_assistant_id needed for sub_assistant type tools
            sub_assistant_id = (
                str(tool_def.assistant_id) if tool_def.assistant_id else None
            )

            tool_instance = None
            tool_class: Optional[Type[Tool]] = None

            # Map tool_type to class
            if tool_type == "reminder":
                tool_class = ReminderTool
            elif tool_type == "time":
                tool_class = TimeToolWrapper
            elif tool_type == "calendar":
                # Calendar tools are differentiated by name from the DB
                if tool_name == "calendar_create":
                    tool_class = CalendarCreateTool
                elif tool_name == "calendar_list":
                    tool_class = CalendarListTool
                else:
                    logger.warning(
                        f"Unknown calendar tool name: {tool_name} for type {tool_type}"
                    )
            elif tool_type == "web_search":
                tool_class = WebSearchTool
            # Example for sub_assistant (assuming a SubAssistantTool class exists)
            # elif tool_type == "sub_assistant":
            #     tool_class = SubAssistantTool
            #     if not sub_assistant_id:
            #         logger.error(f"Sub-assistant ID missing for sub_assistant tool: {tool_name}")
            #         tool_class = None # Prevent instantiation
            else:
                logger.warning(
                    f"Unknown or unsupported tool type: {tool_type} for tool: {tool_name}"
                )

            if tool_class:
                try:
                    # Prepare arguments for BaseTool constructor
                    base_tool_args = {
                        "name": tool_name,
                        "description": tool_description,
                        "settings": self.settings,  # Pass settings
                        "user_id": user_id,
                        "assistant_id": assistant_id,
                        "tool_id": tool_id_str,
                        # args_schema is now typically set in the tool's class definition
                        # or can be passed explicitly if needed:
                        # "args_schema": tool_class.args_schema # Or fetch from tool_def if stored differently
                    }

                    # Add specific args only if needed by a tool (sub_assistant example)
                    # if tool_type == "sub_assistant" and sub_assistant_id:
                    #    base_tool_args["sub_assistant_id"] = sub_assistant_id

                    # Instantiate the tool using the mapped class and BaseTool args
                    tool_instance = tool_class(**base_tool_args)

                    logger.info(
                        f"Initialized tool: {tool_instance.name} (Type: {tool_type}) - Desc: {tool_instance.description}"
                    )
                    tools.append(tool_instance)

                except Exception as e:
                    logger.error(
                        f"Failed to initialize tool '{tool_name}' (Type: {tool_type}): {e}",
                        exc_info=True,
                    )

        return tools

    # async def close(self):
    #     # If RestServiceClient was used, close it here
    #     # await self.rest_client.close()
    #     pass # No client to close at factory level now

    # Future method placeholders if needed
    # def create_openai_functions(self, tool_definitions: List[Dict], ...) -> List[Dict]:
    #     pass
