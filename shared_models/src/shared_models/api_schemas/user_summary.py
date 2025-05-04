from uuid import UUID

from .base import BaseSchema, TimestampSchema


class UserSummaryBase(BaseSchema):
    """Base schema for user summary data."""

    summary_text: str


class UserSummaryCreateUpdate(UserSummaryBase):
    """Schema for creating or updating a user summary."""


class UserSummaryRead(UserSummaryBase, TimestampSchema):
    """Schema for reading a user summary, including timestamps."""

    id: UUID
    # Timestamps are inherited from TimestampSchema
