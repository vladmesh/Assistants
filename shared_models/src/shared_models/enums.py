import enum


# Assistant/Tool related enums
class AssistantType(str, enum.Enum):
    LLM = "llm"  # Direct interaction with LLM via LangGraph


class ToolType(str, enum.Enum):
    CALENDAR = "calendar"
    REMINDER_CREATE = "reminder_create"
    REMINDER_LIST = "reminder_list"
    REMINDER_DELETE = "reminder_delete"
    TIME = "time"
    SUB_ASSISTANT = "sub_assistant"
    WEATHER = "weather"
    WEB_SEARCH = "web_search"
    USER_FACT = "user_fact"


# Reminder related enums
class ReminderType(str, enum.Enum):
    ONE_TIME = "one_time"
    RECURRING = "recurring"


class ReminderStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
