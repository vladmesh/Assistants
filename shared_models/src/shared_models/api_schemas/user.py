from .base import BaseSchema, TimestampSchema


# Schema for creating a user (input)
class TelegramUserCreate(BaseSchema):
    telegram_id: int
    username: str | None = None
    is_active: bool = True


# Schema for updating a user (input, allows partial updates)
class TelegramUserUpdate(BaseSchema):
    username: str | None = None
    timezone: str | None = None
    preferred_name: str | None = None
    is_active: bool | None = None


# Schema for reading a user (output)
class TelegramUserRead(TelegramUserCreate, TimestampSchema):
    id: int  # Internal DB ID
