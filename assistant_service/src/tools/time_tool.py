"""Time-related tools"""

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from tools.base import BaseTool
from utils.error_handler import ToolExecutionError


class TimezoneInput(BaseModel):
    """Schema for timezone input"""

    timezone: str = Field(
        description="Timezone like 'Europe/Paris' or 'America/New_York' or UTC"
    )


class TimeToolWrapper(BaseTool):
    """Tool for getting current time in specified timezone"""

    def __init__(self, user_id: Optional[str] = None):
        super().__init__(
            name="time",
            description="Get current time in specified timezone",
            args_schema=TimezoneInput,
            user_id=user_id,
        )

    async def _execute(self, timezone: str = "UTC") -> str:
        """Get current time in specified timezone

        Args:
            timezone: Timezone name (e.g. 'Europe/Paris')

        Returns:
            Current time in specified timezone as string

        Raises:
            ToolExecutionError: If timezone is invalid or time retrieval fails
            InvalidInputError: If timezone is None or empty
        """
        if timezone is None or timezone.strip() == "":
            timezone = "UTC"

        try:
            tz = ZoneInfo(timezone)
            current_time = datetime.now(tz)
            return current_time.strftime("%Y-%m-%d %H:%M:%S %Z")
        except Exception as e:
            raise ToolExecutionError(f"Error getting time: {str(e)}", self.name)
