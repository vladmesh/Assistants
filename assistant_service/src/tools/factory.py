# assistant_service/src/tools/factory.py
import logging
from typing import TYPE_CHECKING, List, Optional, Type

from config.settings import Settings
from langchain_core.tools import Tool

# Import shared models
from tools.calendar_tool import CalendarCreateTool, CalendarListTool

# Updated import for reminder tools
from tools.reminder_tool import ReminderCreateTool, ReminderDeleteTool, ReminderListTool
from tools.sub_assistant_tool import SubAssistantTool  # Import SubAssistantTool

# Import specific tool implementation classes
from tools.time_tool import TimeToolWrapper
from tools.user_fact_tool import UserFactTool  # Import the new tool
from tools.web_search_tool import WebSearchTool

from shared_models.api_schemas import ToolRead  # Import new schema

if TYPE_CHECKING:
    from assistants.factory import AssistantFactory  # Import for type hinting

logger = logging.getLogger(__name__)


class ToolFactory:
    """Factory class for creating tool instances from definitions."""

    def __init__(
        self, settings: Settings, assistant_factory: Optional["AssistantFactory"] = None
    ):
        """Initializes the factory with necessary settings and assistant factory."""
        self.settings = settings
        self.assistant_factory = assistant_factory  # Store the assistant factory
        if not self.assistant_factory:
            logger.warning(
                "AssistantFactory not provided to ToolFactory. SubAssistantTool cannot be created."
            )

    async def create_langchain_tools(
        self, tool_definitions: List[ToolRead], user_id: str, assistant_id: str
    ) -> List[Tool]:
        """
        Creates Langchain Tool instances from a list of ToolRead definitions.
        Name and Description are now fetched from tool_definitions.
        Args_schema is defined in the tool class.
        Returns a list of successfully initialized tools.
        """
        tools = []
        for tool_def in tool_definitions:
            tool_instance = None  # Reset for each definition
            try:
                tool_type = tool_def.tool_type
                tool_name = tool_def.name  # Get name from DB model
                tool_description = tool_def.description  # Get description from DB model
                tool_id_str = str(tool_def.id)
                # sub_assistant_id needed for sub_assistant type tools
                sub_assistant_id = (
                    str(tool_def.assistant_id) if tool_def.assistant_id else None
                )

                tool_class: Optional[Type[Tool]] = None

                # Map tool_type to class
                if tool_type == "reminder_create":  # Changed from "reminder"
                    tool_class = ReminderCreateTool
                elif tool_type == "reminder_list":
                    tool_class = ReminderListTool
                elif tool_type == "reminder_delete":
                    tool_class = ReminderDeleteTool
                elif tool_type == "time":
                    tool_class = TimeToolWrapper
                elif tool_type == "calendar":
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
                elif tool_type == "user_fact":  # Add handling for the new tool type
                    tool_class = UserFactTool
                elif tool_type == "sub_assistant":
                    if not self.assistant_factory:
                        raise ValueError(
                            "Cannot create SubAssistantTool: AssistantFactory not available."
                        )

                    if not sub_assistant_id:
                        raise ValueError(
                            f"Sub-assistant DB ID missing for sub_assistant tool: {tool_name}"
                        )

                    logger.info(
                        f"Attempting to fetch sub-assistant with ID: {sub_assistant_id}"
                    )
                    # Ensure assistant_factory is not None before calling get_assistant_by_id
                    # This check is technically redundant due to the earlier check, but good for type checkers
                    if self.assistant_factory is None:
                        raise ValueError(
                            "AssistantFactory is None, cannot fetch sub-assistant."
                        )

                    sub_assistant_instance = (
                        await self.assistant_factory.get_assistant_by_id(
                            sub_assistant_id, user_id=user_id
                        )
                    )
                    logger.info(
                        f"Successfully fetched sub-assistant: {sub_assistant_instance.name}"
                    )

                    sub_assistant_tool_args = {
                        "name": tool_name,
                        "description": tool_description,
                        "settings": self.settings,
                        "user_id": user_id,
                        "sub_assistant": sub_assistant_instance,
                        "parent_assistant_id": assistant_id,
                        "sub_assistant_db_id": sub_assistant_id,
                        "tool_id": tool_id_str,
                    }
                    tool_instance = SubAssistantTool(**sub_assistant_tool_args)
                    logger.info(f"Initialized SubAssistantTool: {tool_instance.name}")

                else:
                    logger.warning(
                        f"Unknown or unsupported tool type: {tool_type} for tool: {tool_name}"
                    )

                if (
                    tool_class and not tool_instance
                ):  # Ensure tool_instance isn't already set (e.g. for SubAssistantTool)
                    base_tool_args = {
                        "name": tool_name,
                        "description": tool_description,
                        "settings": self.settings,
                        "user_id": user_id,
                        "assistant_id": assistant_id,
                        "tool_id": tool_id_str,
                    }
                    tool_instance = tool_class(**base_tool_args)
                    logger.info(
                        f"Initialized tool: {tool_instance.name} (Type: {tool_type}) - Desc: {tool_instance.description}"
                    )

                if tool_instance:
                    tools.append(tool_instance)

            except Exception as e:
                logger.error(
                    f"Failed to initialize tool '{tool_def.name}' (Type: {tool_def.tool_type}) for assistant {assistant_id}: {e}",
                    exc_info=True,
                )

        return tools
