# Re-export all api schemas for easier access from shared_models.api_schemas

from .assistant import (
    AssistantBase,
    AssistantCreate,
    AssistantRead,
    AssistantReadSimple,
    AssistantToolLinkBase,
    AssistantToolLinkCreate,
    AssistantToolLinkRead,
    AssistantUpdate,
    ToolBase,
    ToolCreate,
    ToolRead,
    ToolUpdate,
)
from .base import BaseSchema, TimestampSchema
from .calendar import (
    CalendarCredentialsBase,
    CalendarCredentialsCreate,
    CalendarCredentialsRead,
)
from .checkpoint import CheckpointBase, CheckpointCreate, CheckpointRead
from .reminder import ReminderBase, ReminderCreate, ReminderRead, ReminderUpdate
from .user import TelegramUserCreate, TelegramUserRead, TelegramUserUpdate
from .user_fact import UserFactBase, UserFactCreate, UserFactRead
from .user_secretary import (
    UserSecretaryLinkBase,
    UserSecretaryLinkCreate,
    UserSecretaryLinkRead,
)
from .user_summary import UserSummaryBase, UserSummaryCreateUpdate, UserSummaryRead

__all__ = [
    # Base
    "BaseSchema",
    "TimestampSchema",
    # Assistant & Tool
    "AssistantBase",
    "AssistantCreate",
    "AssistantRead",
    "AssistantReadSimple",
    "AssistantUpdate",
    "ToolBase",
    "ToolCreate",
    "ToolRead",
    "ToolUpdate",
    "AssistantToolLinkBase",
    "AssistantToolLinkCreate",
    "AssistantToolLinkRead",
    # Calendar
    "CalendarCredentialsBase",
    "CalendarCredentialsCreate",
    "CalendarCredentialsRead",
    # Checkpoint
    "CheckpointBase",
    "CheckpointCreate",
    "CheckpointRead",
    # Reminder
    "ReminderBase",
    "ReminderCreate",
    "ReminderRead",
    "ReminderUpdate",
    # User
    "TelegramUserCreate",
    "TelegramUserRead",
    "TelegramUserUpdate",
    # UserSecretaryLink
    "UserSecretaryLinkBase",
    "UserSecretaryLinkCreate",
    "UserSecretaryLinkRead",
    # UserFact
    "UserFactBase",
    "UserFactCreate",
    "UserFactRead",
    # UserSummary
    "UserSummaryBase",
    "UserSummaryCreateUpdate",
    "UserSummaryRead",
]
