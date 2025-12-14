"""Time-related tools"""

from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from shared_models import get_logger

from tools.base import BaseTool
from utils.error_handler import ToolExecutionError

logger = get_logger(__name__)


class TimezoneInput(BaseModel):
    """Input schema for the time tool."""

    timezone: str | None = Field(None, description="Timezone, e.g., 'Europe/Moscow'")


class TimeToolWrapper(BaseTool):
    """Wrapper for getting current time with timezone support."""

    # Restore the Type annotation for args_schema
    args_schema: type[TimezoneInput] = TimezoneInput

    # Lazy initialization attribute

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
            raise ToolExecutionError(f"Error getting time: {str(e)}", self.name) from e
