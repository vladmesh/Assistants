# Import models/schemas that should be accessible directly from shared_models

# Legacy api_models import kept commented for now
# from .api_models import UserSecretaryAssignment

# Import the entire api_schemas module
# from . import api_schemas # This line is replaced by specific imports below

# Import all enums
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
    # Other API models (UserSecretaryAssignment removed)
    # "UserSecretaryAssignment",
    # Enums
    "AssistantType",
    "ToolType",
    "ReminderType",
    "ReminderStatus",
    # All API Schemas (re-exported as a module)
    "api_schemas",
]

# If you prefer exporting individual schemas from api_schemas:
# __all__.extend(api_schemas.__all__)
