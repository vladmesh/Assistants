import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from .base import BaseModel


class GlobalSettings(BaseModel, table=True):
    # We use id=1 as a constant for the single row
    id: Optional[int] = Field(default=1, primary_key=True)
    summarization_prompt: str = Field(
        default="Summarize the conversation.",
        description="The prompt used for summarizing conversation history.",
    )
    context_window_size: int = Field(
        default=4096, description="Maximum token limit for the context window."
    )
    # created_at and updated_at are inherited from BaseModel
