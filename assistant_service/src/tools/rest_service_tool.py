"""Tool data validation and transformation from REST service"""

from pydantic import BaseModel

from config.logger import get_logger
from config.settings import Settings

logger = get_logger(__name__)


class RestServiceTool(BaseModel):
    """Tool data from REST service"""

    id: str
    name: str
    tool_type: str
    description: str
    assistant_id: str | None = None  # ID of sub-assistant for sub_assistant type
    is_active: bool = True
    settings: Settings | None = None

    def to_tool(self, secretary_id: str | None = None):
        """Convert REST service tool to actual tool instance"""
        from .calendar_tool import CalendarCreateTool, CalendarListTool
        from .reminder_tool import ReminderTool
        from .sub_assistant_tool import SubAssistantTool
        from .time_tool import TimeToolWrapper
        from .web_search_tool import WebSearchTool

        logger.info(
            "Converting tool",
            name=self.name,
            tool_type=self.tool_type,
            assistant_id=self.assistant_id,
        )

        if self.tool_type == "time":
            logger.info("Creating TimeToolWrapper")
            return TimeToolWrapper()
        elif self.tool_type == "sub_assistant":
            if not self.assistant_id:
                raise ValueError("assistant_id is required for sub_assistant tool type")
            logger.info(
                "Creating SubAssistantTool",
                name=self.name,
                assistant_id=self.assistant_id,
            )
            tool = SubAssistantTool(
                sub_assistant=None,  # Will be set later
                assistant_id=self.assistant_id,
                name=self.name,
                description=self.description,
                user_id=None,  # Will be set later
            )
            logger.info(
                "Created SubAssistantTool",
                name=tool.name,
                assistant_id=tool.assistant_id,
            )
            return tool
        elif self.tool_type == "reminder":
            logger.info("Creating ReminderTool", assistant_id=secretary_id)
            return ReminderTool(assistant_id=secretary_id)
        elif self.tool_type == "calendar":
            if not self.settings:
                raise ValueError("settings is required for calendar tools")
            if self.name == "calendar_create":
                logger.info("Creating CalendarCreateTool")
                return CalendarCreateTool(
                    settings=self.settings, user_id=None
                )  # Will be set later
            elif self.name == "calendar_list":
                logger.info("Creating CalendarListTool")
                return CalendarListTool(
                    settings=self.settings, user_id=None
                )  # Will be set later
            else:
                raise ValueError(f"Unknown calendar tool name: {self.name}")
        elif self.tool_type == "web_search":
            if not self.settings:
                raise ValueError("settings is required for web_search tool")
            logger.info("Creating WebSearchTool")
            return WebSearchTool(
                settings=self.settings, user_id=None
            )  # Will be set later
        else:
            raise ValueError(f"Unknown tool type: {self.tool_type}")
