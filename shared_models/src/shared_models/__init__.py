# Import models/schemas that should be accessible directly from shared_models

# Import the single remaining model from api_models
# from .api_models import UserSecretaryAssignment # This line should be removed or commented out

# Import the entire api_schemas module
from . import api_schemas

# Import all enums
from .enums import AssistantType, ReminderStatus, ReminderType, ToolType

# Import queue models
from .queue import (
    AssistantResponseMessage,
    HumanQueueMessageContent,
    QueueMessage,
    QueueMessageSource,
    QueueMessageType,
    QueueTrigger,
    ToolQueueMessageContent,
    TriggerType,
)

__all__ = [
    # Queue models
    "AssistantResponseMessage",
    "QueueMessage",
    "HumanQueueMessageContent",
    "ToolQueueMessageContent",
    "QueueMessageSource",
    "QueueMessageType",
    "QueueTrigger",
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
