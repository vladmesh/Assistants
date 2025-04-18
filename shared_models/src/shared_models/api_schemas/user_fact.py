from uuid import UUID

from .base import BaseSchema, TimestampSchema


class UserFactBase(BaseSchema):
    fact: str
    user_id: int  # Include user_id here as it's essential


class UserFactCreate(UserFactBase):
    # No additional fields needed if user_id is in Base
    pass


class UserFactRead(UserFactBase, TimestampSchema):
    id: UUID
    # user_id is inherited from UserFactBase
    # created_at, updated_at are inherited from TimestampSchema
