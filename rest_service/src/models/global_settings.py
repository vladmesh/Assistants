from typing import Optional

from sqlmodel import Field, SQLModel

# Assuming base.py exists in the same directory and defines BaseModel
# If not, adjust the import path accordingly.
from .base import BaseModel


class GlobalSettings(BaseModel, table=True):
    # Используем id=1 как константу для единственной строки
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
