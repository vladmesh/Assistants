import datetime

from pydantic import Field

from .base import BaseSchema


class GlobalSettingsBase(BaseSchema):
    summarization_prompt: str = Field(
        ..., description="The prompt used for summarizing conversation history."
    )
    context_window_size: int = Field(
        ..., gt=0, description="Maximum token limit for the context window (> 0)."
    )

    class Config:
        from_attributes = True  # Для совместимости с SQLModel/ORM


# Модель для чтения (включает id и timestamp)
class GlobalSettingsRead(GlobalSettingsBase):
    id: int
    updated_at: datetime.datetime


# Модель для обновления (все поля опциональны)
class GlobalSettingsUpdate(BaseSchema):
    summarization_prompt: str | None = Field(
        default=None,
        description="The prompt used for summarizing conversation history.",
    )
    context_window_size: int | None = Field(
        default=None,
        gt=0,
        description="Maximum token limit for the context window (> 0).",
    )
