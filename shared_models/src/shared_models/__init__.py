# Import models/schemas that should be accessible directly from shared_models

# Import specific API schemas
from .api_schemas import (
    AssistantCreate,
    AssistantRead,
    AssistantUpdate,
    ToolCreate,
    ToolRead,
)

# Import Memory schemas
from .api_schemas.memory import MemoryCreate, MemoryRead, MemoryUpdate
from .enums import AssistantType, ReminderStatus, ReminderType, ToolType

# Import remaining queue models
from .queue import (
    AssistantResponseMessage,
    HumanQueueMessage,
    QueueMessage,
    QueueMessageContent,
    QueueMessageSource,
    QueueMessageType,
    QueueTrigger,
    ToolQueueMessage,
    TriggerType,
)

# Note: LLM providers are available via shared_models.llm_providers
# but not imported at top level to avoid requiring openai in all services

__all__ = [
    # Queue models
    "AssistantResponseMessage",
    "HumanQueueMessage",
    "QueueMessage",
    "QueueMessageContent",
    "QueueMessageSource",
    "QueueMessageType",
    "QueueTrigger",
    "ToolQueueMessage",
    "TriggerType",
    # Enums
    "AssistantType",
    "ToolType",
    "ReminderType",
    "ReminderStatus",
    # API Schemas
    "api_schemas",
]
