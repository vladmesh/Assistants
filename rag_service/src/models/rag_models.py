from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class RagData(BaseModel):
    """Модель для данных, хранящихся в RAG сервисе."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    text: str = Field(..., description="Текстовое содержимое")
    embedding: List[float] = Field(..., description="Векторное представление текста")
    data_type: str = Field(
        ...,
        description="Тип данных (например, 'shared_rule', 'user_history', 'assistant_note')",
    )
    user_id: Optional[int] = Field(
        None, description="ID пользователя, если данные специфичны для пользователя"
    )
    assistant_id: Optional[UUID] = Field(
        None, description="ID ассистента, если данные специфичны для ассистента"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SearchQuery(BaseModel):
    """Модель для поисковых запросов к RAG сервису."""

    query_embedding: List[float] = Field(
        ..., description="Векторное представление запроса"
    )
    data_type: str = Field(..., description="Тип данных для поиска")
    user_id: Optional[int] = Field(None, description="Фильтр по ID пользователя")
    assistant_id: Optional[UUID] = Field(None, description="Фильтр по ID ассистента")
    top_k: int = Field(default=5, description="Количество результатов для возврата")


class SearchResult(BaseModel):
    """Модель для результатов поиска из RAG сервиса."""

    id: UUID
    text: str
    distance: float
    metadata: Dict[str, Any]
