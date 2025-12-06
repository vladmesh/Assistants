from typing import TYPE_CHECKING, Annotated
from uuid import UUID, uuid4

# Import enums from shared_models
from shared_models.enums import AssistantType, ToolType
from sqlalchemy import Column, String
from sqlmodel import Field, Relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .message import Message
    from .reminder import Reminder
    from .user_secretary import UserSecretaryLink
    from .user_summary import UserSummary


class AssistantToolLink(BaseModel, table=True):
    """Связь между ассистентом и инструментом"""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    assistant_id: UUID = Field(foreign_key="assistant.id", index=True)
    tool_id: UUID = Field(foreign_key="tool.id", index=True)
    sub_assistant_id: UUID | None = Field(
        default=None, foreign_key="assistant.id", index=True
    )
    is_active: bool = Field(default=True, index=True)

    class Config:
        table_name = "assistant_tool_link"


class Assistant(BaseModel, table=True):
    """Модель ассистента"""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True)
    is_secretary: bool = Field(default=False, index=True)
    model: str  # gpt-4, gpt-3.5-turbo и т.д.
    instructions: str  # Промпт/инструкции для ассистента
    description: str | None = Field(default=None)  # Description for user selection
    startup_message: str | None = Field(
        default=None
    )  # Message to send when user selects this secretary
    assistant_type: Annotated[str, AssistantType] = Field(
        sa_column=Column(String), default=AssistantType.LLM.value
    )
    is_active: bool = Field(default=True, index=True)

    # Relationships
    tools: list["Tool"] = Relationship(
        link_model=AssistantToolLink,
        sa_relationship_kwargs={
            "foreign_keys": [AssistantToolLink.assistant_id],
            "primaryjoin": "Assistant.id == AssistantToolLink.assistant_id",
            "secondaryjoin": (
                "and_(Tool.id == foreign(AssistantToolLink.tool_id), "
                "AssistantToolLink.is_active == True)"
            ),
        },
    )
    user_links: list["UserSecretaryLink"] = Relationship(
        back_populates="secretary", sa_relationship_kwargs={"lazy": "selectin"}
    )
    user_summaries: list["UserSummary"] = Relationship(back_populates="assistant")
    reminders: list["Reminder"] = Relationship(
        back_populates="assistant",
        sa_relationship_kwargs={
            "foreign_keys": "[Reminder.assistant_id]",
            "cascade": "all, delete-orphan",
        },
    )
    messages: list["Message"] = Relationship(back_populates="assistant")

    def validate_type(self) -> None:
        """Проверяет корректность типа ассистента"""
        if self.assistant_type not in [t.value for t in AssistantType]:
            raise ValueError("Invalid assistant type")


class Tool(BaseModel, table=True):
    """Модель инструмента"""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True)  # Название инструмента
    tool_type: Annotated[str, ToolType] = Field(
        sa_column=Column(String), default=ToolType.TIME.value
    )
    description: str
    assistant_id: UUID | None = Field(
        default=None, foreign_key="assistant.id", index=True
    )  # Для sub_assistant, ссылка на ассистента, которого вызывает данный инструмент
    is_active: bool = Field(default=True, index=True)

    def validate_type(self) -> None:
        """Проверяет корректность типа инструмента"""
        if self.tool_type not in [t.value for t in ToolType]:
            raise ValueError("Invalid tool type")
