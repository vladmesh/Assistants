import enum


# Assistant/Tool related enums
class AssistantType(str, enum.Enum):
    LLM = "llm"  # Direct interaction with LLM
    OPENAI_API = "openai_api"  # Interaction via OpenAI Assistants API


class ToolType(str, enum.Enum):
    CALENDAR = "calendar"
    REMINDER = "reminder"
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
