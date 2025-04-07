# assistant_service/src/tools/factory.py
import logging
from typing import Dict, List, Optional

from config.settings import Settings
from langchain_core.tools import Tool
from tools.calendar_tool import CalendarCreateTool, CalendarListTool
from tools.reminder_tool import ReminderTool

# Import specific tool implementation classes
from tools.time_tool import TimeToolWrapper
from tools.web_search_tool import WebSearchTool

# Import other tools as needed
# from tools.rest_service_tool import RestServiceTool # Example if needed

logger = logging.getLogger(__name__)


class ToolFactory:
    """Factory class for creating tool instances from definitions."""

    def __init__(self, settings: Settings):
        """Initializes the factory with necessary settings."""
        self.settings = settings
        # Potential place for caching initialized tools if needed later
        # self.tool_cache = {}

    def create_langchain_tools(
        self,
        tool_definitions: List[Dict],
        user_id: str,  # user_id is now required
        assistant_id: Optional[str] = None,  # assistant_id is optional
    ) -> List[Tool]:
        """
        Creates a list of Langchain Tool instances based on raw definitions.

        Args:
            tool_definitions: List of dictionaries representing raw tool definitions.
            user_id: The ID of the user for whom the tools are being created.
            assistant_id: The ID of the assistant instance, required by some tools.

        Returns:
            A list of initialized Langchain Tool instances.
        """
        initialized_tools: List[Tool] = []
        if not tool_definitions:
            logger.debug("No tool definitions provided, returning empty list.")
            return initialized_tools

        for tool_def in tool_definitions:
            tool_type = tool_def.get("tool_type")
            tool_name = tool_def.get("name")
            # Get tool-specific config if provided in the definition
            tool_config = tool_def.get("config", {})
            log_extra = {
                "assistant_id": assistant_id,
                "user_id": user_id,
                "tool_name": tool_name,
                "tool_type": tool_type,
            }
            tool_instance: Optional[Tool] = None

            try:
                if tool_type == "time":
                    # Time tool doesn't need user_id or assistant_id
                    # Pass config if TimeToolWrapper supports it
                    tool_instance = TimeToolWrapper(**tool_config)
                    logger.info("Initialized time tool", extra=log_extra)

                elif tool_type == "web_search":
                    # Web search might need API key from settings
                    tavily_api_key = self.settings.TAVILY_API_KEY
                    if tavily_api_key:
                        # Pass config if WebSearchTool supports it
                        tool_instance = WebSearchTool(
                            tavily_api_key=tavily_api_key, **tool_config
                        )
                        logger.info("Initialized web_search tool", extra=log_extra)
                    else:
                        logger.warning(
                            "TAVILY_API_KEY not set. Skipping WebSearchTool.",
                            extra=log_extra,
                        )

                elif tool_type == "calendar":
                    # Calendar tools likely need user_id
                    # Pass user_id and config
                    if tool_name == "calendar_create":
                        tool_instance = CalendarCreateTool(
                            user_id=user_id, **tool_config
                        )
                        logger.info("Initialized calendar_create tool", extra=log_extra)
                    elif tool_name == "calendar_list":
                        tool_instance = CalendarListTool(user_id=user_id, **tool_config)
                        logger.info("Initialized calendar_list tool", extra=log_extra)
                    else:
                        logger.warning(
                            f"Unknown calendar tool name: {tool_name}. Skipping.",
                            extra=log_extra,
                        )

                elif tool_type == "reminder":
                    # Reminder tool needs assistant_id and user_id
                    if not assistant_id:
                        logger.warning(
                            "assistant_id is required for ReminderTool. Skipping.",
                            extra=log_extra,
                        )
                    else:
                        tool_instance = ReminderTool(
                            user_id=user_id, assistant_id=assistant_id, **tool_config
                        )
                        logger.info("Initialized reminder tool", extra=log_extra)

                elif tool_type == "sub_assistant":
                    # Handling sub_assistants might require the AssistantFactory
                    # Skipping initialization via ToolFactory for now.
                    logger.warning(
                        "sub_assistant tool type not supported by ToolFactory yet. Skipping.",
                        extra=log_extra,
                    )

                # Add other tool types here as needed
                # elif tool_type == "rest":
                #     tool_instance = RestServiceToolImplementation(...)

                else:
                    logger.warning(
                        f"Unknown tool type '{tool_type}'. Cannot initialize. Skipping.",
                        extra=log_extra,
                    )

                if tool_instance:
                    initialized_tools.append(tool_instance)

            except Exception as e:
                # Log the error and continue with the next tool
                logger.error(
                    f"Failed to initialize tool '{tool_name}' of type '{tool_type}'. Error: {e}",
                    extra=log_extra,
                    exc_info=True,
                )

        logger.info(f"Initialized {len(initialized_tools)} tools for user {user_id}")
        return initialized_tools

    # Future method placeholders if needed
    # def create_openai_functions(self, tool_definitions: List[Dict], ...) -> List[Dict]:
    #     pass
