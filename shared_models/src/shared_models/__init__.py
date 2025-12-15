# Import models/schemas that should be accessible directly from shared_models

# Import logging utilities
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
from .logging import (
    LogEventType,
    LogLevel,
    clear_context,
    clear_correlation_id,
    clear_user_id,
    configure_logging,
    get_correlation_id,
    get_logger,
    get_user_id,
    set_correlation_id,
    set_user_id,
)

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
from .queue_logger import QueueDirection, QueueLogger

# Note: LLM providers are available via shared_models.llm_providers
# but not imported at top level to avoid requiring openai in all services

__all__ = [
    # Logging
    "LogEventType",
    "LogLevel",
    "configure_logging",
    "get_logger",
    "set_correlation_id",
    "get_correlation_id",
    "clear_correlation_id",
    "set_user_id",
    "get_user_id",
    "clear_user_id",
    "clear_context",
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
    "QueueDirection",
    "QueueLogger",
    # Enums
    "AssistantType",
    "ToolType",
    "ReminderType",
    "ReminderStatus",
    # API Schemas
    "api_schemas",
]
