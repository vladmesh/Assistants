# Import new API models
from shared_models.api_models import (
    AssistantModel,
    CreateReminderRequest,
    ReminderModel,
    ReminderStatus,
    ReminderType,
    ToolModel,
    UserModel,
)

# Update queue imports: remove old, add new
from shared_models.queue import HumanQueueMessageContent  # Keep content model import
from shared_models.queue import QueueTrigger  # Added
from shared_models.queue import ToolQueueMessageContent  # Keep content model import
from shared_models.queue import TriggerType  # Added
from shared_models.queue import (  # HumanQueueMessage, # Removed; ToolQueueMessage, # Removed
    QueueMessage,
    QueueMessageSource,
    QueueMessageType,
)

__all__ = [
    # Queue models
    "QueueMessage",
    "HumanQueueMessageContent",  # Re-added to export
    "ToolQueueMessageContent",  # Re-added to export
    "QueueMessageSource",
    "QueueMessageType",
    # "ToolQueueMessage", # Removed
    # "HumanQueueMessage", # Removed
    "QueueTrigger",  # Added
    "TriggerType",  # Added
    # API models
    "AssistantModel",
    "ToolModel",
    "UserModel",
    "ReminderModel",
    "CreateReminderRequest",
    "ReminderType",
    "ReminderStatus",
]
