from typing import Optional

from .base import BaseSchema, TimestampSchema


# Schema for creating a user (input)
class TelegramUserCreate(BaseSchema):
    telegram_id: int
    username: Optional[str] = None
    is_active: bool = True


# Schema for updating a user (input, allows partial updates)
class TelegramUserUpdate(BaseSchema):
    username: Optional[str] = None
    timezone: Optional[str] = None
    preferred_name: Optional[str] = None
    is_active: Optional[bool] = None


# Schema for reading a user (output)
class TelegramUserRead(TelegramUserCreate, TimestampSchema):
    id: int  # Internal DB ID
