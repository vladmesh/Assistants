from uuid import UUID

from .base import BaseSchema, TimestampSchema


class UserSummaryBase(BaseSchema):
    """Base schema for user summary data."""

    summary_text: str
    user_id: int
    assistant_id: UUID
    last_message_id_covered: int | None = None
    token_count: int | None = None


class UserSummaryCreateUpdate(UserSummaryBase):
    """Schema for creating or updating a user summary."""


class UserSummaryRead(UserSummaryBase, TimestampSchema):
    """Schema for reading a user summary, including timestamps."""

    id: int
    # Timestamps are inherited from TimestampSchema
