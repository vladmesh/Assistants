"""Tool data validation and transformation from REST service"""
from typing import Optional
from pydantic import BaseModel
from config.settings import Settings

class RestServiceTool(BaseModel):
    """Tool data from REST service"""
    id: str
    name: str
    tool_type: str
    description: str
    assistant_id: Optional[str] = None  # ID of sub-assistant for sub_assistant type
    input_schema: Optional[str] = None
    is_active: bool = True
    settings: Optional[Settings] = None

    def to_tool(self):
        """Convert REST service tool to actual tool instance"""
        from .time_tool import TimeToolWrapper
        from .sub_assistant_tool import SubAssistantTool
        from .reminder_tool import ReminderTool
        from .calendar_tool import CalendarCreateTool, CalendarListTool

        if self.tool_type == "time":
            return TimeToolWrapper()
        elif self.tool_type == "sub_assistant":
            if not self.assistant_id:
                raise ValueError("assistant_id is required for sub_assistant tool type")
            return SubAssistantTool(
                sub_assistant=None,  # Will be set later
                assistant_id=self.assistant_id,
                name=self.name,
                description=self.description,
                user_id=None  # Will be set later
            )
        elif self.tool_type == "reminder":
            return ReminderTool()
        elif self.tool_type == "calendar":
            if not self.settings:
                raise ValueError("settings is required for calendar tools")
            if self.name == "calendar_create":
                return CalendarCreateTool(settings=self.settings)
            elif self.name == "calendar_list":
                return CalendarListTool(settings=self.settings)
            else:
                raise ValueError(f"Unknown calendar tool name: {self.name}")
        else:
            raise ValueError(f"Unknown tool type: {self.tool_type}") 