import enum
from datetime import UTC, datetime
from typing import Annotated, Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import String
from sqlalchemy.orm import foreign
from sqlmodel import Field, Relationship

from .base import BaseModel


class AssistantType(str, enum.Enum):
    LLM = "llm"  # Прямая работа с LLM
    OPENAI_API = "openai_api"  # Работа через OpenAI Assistants API


class ToolType(str, enum.Enum):
    CALENDAR = "calendar"
    REMINDER = "reminder"
    TIME = "time"
    SUB_ASSISTANT = "sub_assistant"
    WEATHER = "weather"


class AssistantToolLink(BaseModel, table=True):
    """Связь между ассистентом и инструментом"""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    assistant_id: UUID = Field(foreign_key="assistant.id", index=True)
    tool_id: UUID = Field(foreign_key="tool.id", index=True)
    sub_assistant_id: Optional[UUID] = Field(
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
    assistant_type: Annotated[str, AssistantType] = Field(
        sa_column=Column(String), default=AssistantType.LLM.value
    )
    openai_assistant_id: Optional[str] = Field(default=None, index=True)
    is_active: bool = Field(default=True, index=True)

    # Relationships
    tools: List["Tool"] = Relationship(
        back_populates="assistants",
        link_model=AssistantToolLink,
        sa_relationship_kwargs={
            "foreign_keys": [AssistantToolLink.assistant_id],
            "primaryjoin": "Assistant.id == AssistantToolLink.assistant_id",
            "secondaryjoin": "and_(Tool.id == foreign(AssistantToolLink.tool_id), AssistantToolLink.is_active == True)",
        },
    )
    user_links: List["UserSecretaryLink"] = Relationship(
        back_populates="secretary", sa_relationship_kwargs={"lazy": "selectin"}
    )

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
    input_schema: Optional[str] = Field(
        default=None
    )  # JSON схема входных данных в виде строки
    assistant_id: Optional[UUID] = Field(
        default=None, foreign_key="assistant.id", index=True
    )  # Для sub_assistant, ссылка на ассистента, которого вызывает данный инструмент
    is_active: bool = Field(default=True, index=True)

    # Relationships
    assistants: List[Assistant] = Relationship(
        back_populates="tools",
        link_model=AssistantToolLink,
        sa_relationship_kwargs={
            "foreign_keys": [AssistantToolLink.tool_id],
            "primaryjoin": "Tool.id == AssistantToolLink.tool_id",
            "secondaryjoin": "and_(Assistant.id == foreign(AssistantToolLink.assistant_id), AssistantToolLink.is_active == True)",
        },
    )

    def validate_type(self) -> None:
        """Проверяет корректность типа инструмента"""
        if self.tool_type not in [t.value for t in ToolType]:
            raise ValueError("Invalid tool type")

    def validate_schema(self) -> None:
        """Проверяет корректность JSON схемы"""
        if self.input_schema is not None:
            try:
                import json

                json.loads(self.input_schema)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON schema")


class UserAssistantThread(BaseModel, table=True):
    """Хранение thread_id для каждого пользователя и ассистента"""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: str = Field(index=True)  # ID пользователя из TelegramUser
    assistant_id: UUID = Field(foreign_key="assistant.id", index=True)
    thread_id: str  # Thread ID от OpenAI
    last_used: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)

    class Config:
        table_name = "user_assistant_threads"
        unique_together = [
            ("user_id", "assistant_id")
        ]  # Один тред на пару пользователь-ассистент
