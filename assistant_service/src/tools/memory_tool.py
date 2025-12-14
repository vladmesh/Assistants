# assistant_service/src/tools/memory_tool.py
"""Memory tools for Memory V2 - saves and searches memories via RAG service."""

import time

import httpx
from pydantic import BaseModel, Field

from config.logger import get_logger
from tools.base import BaseTool
from utils.error_handler import ToolError

logger = get_logger(__name__)


class MemorySaveSchema(BaseModel):
    """Schema for saving a memory."""

    text: str = Field(
        ...,
        description="Текст воспоминания/факта для сохранения. "
        "Должен быть информативным и конкретным.",
    )
    memory_type: str = Field(
        default="user_fact",
        description="Тип воспоминания: user_fact (факты о пользователе), "
        "preference (предпочтения), event (события), "
        "conversation_insight (инсайты из разговора).",
    )
    importance: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Важность воспоминания от 1 (низкая) до 10 (критическая).",
    )


class MemorySearchSchema(BaseModel):
    """Schema for searching memories."""

    query: str = Field(
        ...,
        description="Текстовый запрос для поиска релевантных воспоминаний. "
        "Используй естественный язык.",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Максимальное количество результатов для возврата.",
    )


class MemorySaveTool(BaseTool):
    """Инструмент для сохранения воспоминаний о пользователе.

    Использует Memory V2 API через RAG service, который автоматически
    генерирует эмбеддинги для семантического поиска.
    """

    args_schema: type[MemorySaveSchema] = MemorySaveSchema
    _client: httpx.AsyncClient | None = None

    def get_client(self) -> httpx.AsyncClient:
        """Lazily initialize and return the httpx client."""
        if self._client is None:
            base_url = self.settings.RAG_SERVICE_URL if self.settings else None
            if not base_url:
                logger.error(
                    "RAG Service URL not configured in settings",
                    tool_name=self.name,
                )
                raise ToolError(
                    "RAG Service URL not configured",
                    self.name,
                    "CONFIGURATION_ERROR",
                )
            self._client = httpx.AsyncClient(base_url=base_url, timeout=30.0)
        return self._client

    async def _execute(
        self,
        text: str,
        memory_type: str = "user_fact",
        importance: int = 5,
    ) -> str:
        """Сохраняет воспоминание о пользователе через RAG service."""
        start_time = time.perf_counter()
        log_extra = {
            "tool_name": self.name,
            "user_id": self.user_id,
            "assistant_id": self.assistant_id,
            "memory_type": memory_type,
            "importance": importance,
        }

        if not self.user_id:
            raise ToolError(
                message="User ID is required to save a memory.",
                tool_name=self.name,
                error_code="USER_ID_REQUIRED",
            )

        try:
            user_id_int = int(self.user_id)
        except ValueError:
            raise ToolError(
                message="Invalid User ID format. Expected an integer.",
                tool_name=self.name,
                error_code="INVALID_USER_ID_FORMAT",
            ) from None

        payload = {
            "user_id": user_id_int,
            "text": text,
            "memory_type": memory_type,
            "importance": importance,
        }
        if self.assistant_id:
            payload["assistant_id"] = self.assistant_id

        try:
            start_api_time = time.perf_counter()
            http_client = self.get_client()
            response = await http_client.post(
                "/api/memory/",
                json=payload,
            )
            api_duration_ms = round((time.perf_counter() - start_api_time) * 1000)
            log_extra["api_duration_ms"] = api_duration_ms

            response.raise_for_status()

            duration_ms = round((time.perf_counter() - start_time) * 1000)
            log_extra["duration_ms"] = duration_ms
            logger.info("Successfully saved memory", **log_extra)

            return "Воспоминание успешно сохранено."

        except httpx.HTTPStatusError as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000)
            log_extra["duration_ms"] = duration_ms
            log_extra["http_status"] = e.response.status_code
            log_extra["response_text"] = e.response.text
            logger.error("API call failed", error=str(e), **log_extra)
            raise ToolError(
                message=(
                    f"Ошибка API при сохранении воспоминания "
                    f"({e.response.status_code}): {e.response.text}"
                ),
                tool_name=self.name,
                error_code="API_ERROR",
            ) from e

        except httpx.RequestError as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000)
            log_extra["duration_ms"] = duration_ms
            logger.error("Network error during execution", error=str(e), **log_extra)
            raise ToolError(
                message=f"Сетевая ошибка при сохранении воспоминания: {e}",
                tool_name=self.name,
                error_code="NETWORK_ERROR",
            ) from e


class MemorySearchTool(BaseTool):
    """Инструмент для поиска релевантных воспоминаний о пользователе.

    Использует семантический поиск через RAG service и pgvector.
    """

    args_schema: type[MemorySearchSchema] = MemorySearchSchema
    _client: httpx.AsyncClient | None = None

    def get_client(self) -> httpx.AsyncClient:
        """Lazily initialize and return the httpx client."""
        if self._client is None:
            base_url = self.settings.RAG_SERVICE_URL if self.settings else None
            if not base_url:
                logger.error(
                    "RAG Service URL not configured in settings",
                    tool_name=self.name,
                )
                raise ToolError(
                    "RAG Service URL not configured",
                    self.name,
                    "CONFIGURATION_ERROR",
                )
            self._client = httpx.AsyncClient(base_url=base_url, timeout=30.0)
        return self._client

    async def _execute(
        self,
        query: str,
        limit: int = 5,
    ) -> str:
        """Ищет релевантные воспоминания о пользователе."""
        start_time = time.perf_counter()
        log_extra = {
            "tool_name": self.name,
            "user_id": self.user_id,
            "assistant_id": self.assistant_id,
            "query_length": len(query),
            "limit": limit,
        }

        if not self.user_id:
            raise ToolError(
                message="User ID is required to search memories.",
                tool_name=self.name,
                error_code="USER_ID_REQUIRED",
            )

        try:
            user_id_int = int(self.user_id)
        except ValueError:
            raise ToolError(
                message="Invalid User ID format. Expected an integer.",
                tool_name=self.name,
                error_code="INVALID_USER_ID_FORMAT",
            ) from None

        payload = {
            "query": query,
            "user_id": user_id_int,
            "limit": limit,
            "threshold": 0.5,  # Lower threshold to get more results
        }

        try:
            start_api_time = time.perf_counter()
            http_client = self.get_client()
            response = await http_client.post(
                "/api/memory/search",
                json=payload,
            )
            api_duration_ms = round((time.perf_counter() - start_api_time) * 1000)
            log_extra["api_duration_ms"] = api_duration_ms

            response.raise_for_status()
            results = response.json()

            duration_ms = round((time.perf_counter() - start_time) * 1000)
            log_extra["duration_ms"] = duration_ms
            log_extra["results_count"] = len(results)
            logger.info("Memory search completed", **log_extra)

            if not results:
                return "Релевантных воспоминаний не найдено."

            # Format results for the LLM
            formatted_results = []
            for i, memory in enumerate(results, 1):
                text = memory.get("text", "")
                memory_type = memory.get("memory_type", "unknown")
                score = memory.get("score", 0)
                formatted_results.append(
                    f"{i}. [{memory_type}] (релевантность: {score:.2f}): {text}"
                )

            return "Найденные воспоминания:\n" + "\n".join(formatted_results)

        except httpx.HTTPStatusError as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000)
            log_extra["duration_ms"] = duration_ms
            log_extra["http_status"] = e.response.status_code
            log_extra["response_text"] = e.response.text
            logger.error("API call failed", error=str(e), **log_extra)
            raise ToolError(
                message=(
                    f"Ошибка API при поиске воспоминаний "
                    f"({e.response.status_code}): {e.response.text}"
                ),
                tool_name=self.name,
                error_code="API_ERROR",
            ) from e

        except httpx.RequestError as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000)
            log_extra["duration_ms"] = duration_ms
            logger.error("Network error during execution", error=str(e), **log_extra)
            raise ToolError(
                message=f"Сетевая ошибка при поиске воспоминаний: {e}",
                tool_name=self.name,
                error_code="NETWORK_ERROR",
            ) from e
