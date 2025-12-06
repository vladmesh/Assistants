# This file makes Python treat the 'crud' directory as a package.

from . import message, user_secretary
from .assistant import (  # noqa: F401
    create_assistant,
    delete_assistant,
    get_assistant,
    get_assistants,
    update_assistant,
)
from .assistant_tool import (  # noqa: F401
    add_tool_to_assistant,
    get_assistant_tools,
    remove_tool_from_assistant,
)
from .calendar import (  # noqa: F401; Renamed/Aliased
    create_or_update_credentials as create_or_update_calendar_credentials,
)
from .calendar import (
    delete_credentials as delete_calendar_credentials,  # Renamed/Aliased
)
from .calendar import get_credentials as get_calendar_credentials  # Renamed/Aliased
from .global_settings import (  # noqa: F401
    create_default_global_settings,
    get_global_settings,
    upsert_global_settings,
)
from .reminder import (  # noqa: F401; Renamed/Aliased
    get_user_reminders as get_reminders_by_user,
)
from .reminder import update_reminder_status  # Changed from update_reminder
from .tool import (  # noqa: F401
    create_tool,
    delete_tool,
    get_tool,
    get_tools,
    update_tool,
)
from .user import get_user_by_id as get_user  # noqa: F401
from .user_secretary import (  # noqa: F401; Renamed/Aliased
    assign_secretary_to_user as create_user_secretary_link,
)
from .user_secretary import (
    deactivate_secretary_assignment as delete_user_secretary_link,  # Renamed/Aliased
)
from .user_secretary import (
    get_secretary_assignment as get_user_secretary_link,  # Renamed/Aliased
)

__all__ = [
    "assistant",
    "tool",
    "user",
    "reminder",
    "calendar",
    "checkpoint",
    "user_secretary",
    "global_settings",
    "message",
]
