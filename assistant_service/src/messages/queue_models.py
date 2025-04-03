from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class QueueMessageType(str, Enum):
    """Типы сообщений в очереди"""

    TOOL = "tool_message"
    HUMAN = "human_message"


class QueueMessageSource(str, Enum):
    """Источники сообщений в очереди"""

    CRON = "cron"
    CALENDAR = "calendar"
    USER = "user"


class QueueMessageContent(BaseModel):
    """Содержимое сообщения очереди"""

    message: str = Field(..., description="Текст сообщения")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Дополнительные данные"
    )


class QueueMessage(BaseModel):
    """Базовый класс для всех сообщений в очереди"""

    type: QueueMessageType = Field(..., description="Тип сообщения")
    user_id: int = Field(..., description="ID пользователя в базе данных")
    source: QueueMessageSource = Field(..., description="Источник сообщения")
    content: QueueMessageContent = Field(..., description="Содержимое сообщения")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(), description="Время создания сообщения"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Преобразует сообщение в словарь"""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QueueMessage":
        """Создает сообщение из словаря"""
        return cls(**data)


class ToolQueueMessage(QueueMessage):
    """Сообщение от инструмента"""

    type: QueueMessageType = Field(
        default=QueueMessageType.TOOL, description="Тип сообщения"
    )
    tool_name: str = Field(..., description="Название инструмента")


class HumanQueueMessage(QueueMessage):
    """Сообщение от пользователя"""

    type: QueueMessageType = Field(
        default=QueueMessageType.HUMAN, description="Тип сообщения"
    )
    chat_id: Optional[int] = Field(None, description="ID чата в Telegram")
