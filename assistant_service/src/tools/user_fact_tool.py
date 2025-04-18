# assistant_service/src/tools/user_fact_tool.py
import time
from typing import Optional, Type

import httpx
from config.logger import get_logger
from pydantic import BaseModel, Field
from tools.base import BaseTool
from utils.error_handler import ToolError

from shared_models.api_schemas.user_fact import (
    UserFactCreate,  # Import the correct schema
)

logger = get_logger(__name__)


class UserFactSchema(BaseModel):
    """Schema for user fact creation input validation."""

    fact: str = Field(..., description="Факт о пользователе, который нужно сохранить.")


class UserFactTool(BaseTool):
    """Инструмент для добавления факта о пользователе."""

    # Use the input schema for args validation
    args_schema: Type[UserFactSchema] = UserFactSchema

    # Add lazy client initialization similar to ReminderTool
    _client: Optional[httpx.AsyncClient] = None

    def get_client(self) -> httpx.AsyncClient:
        """Lazily initialize and return the httpx client."""
        if self._client is None:
            # You might want to configure timeout from self.settings if available
            # Ensure settings are available and contain rest_service_url
            # Use the correct property name (uppercase)
            base_url = self.settings.REST_SERVICE_URL if self.settings else None
            if not base_url:
                logger.error(
                    f"REST Service URL not configured in settings for {self.name}"
                )
                # Raise an error or handle appropriately
                raise ToolError(
                    "REST Service URL not configured", self.name, "CONFIGURATION_ERROR"
                )

            self._client = httpx.AsyncClient(base_url=base_url, timeout=30.0)
            logger.debug(
                f"Initialized httpx client for {self.name} with base URL: {base_url}"
            )
        return self._client

    async def _execute(
        self,
        fact: str,
    ) -> str:
        """Добавляет факт о пользователе через REST API."""
        start_time = time.perf_counter()
        log_extra = {
            "tool_name": self.name,
            "user_id": self.user_id,
            "assistant_id": self.assistant_id,
        }
        logger.debug(f"Executing {self.name} tool", extra=log_extra)

        if not self.user_id:
            raise ToolError(
                message="User ID is required to add a fact.",
                tool_name=self.name,
                error_code="USER_ID_REQUIRED",
            )

        # Input validation happens automatically via BaseTool/Langchain if args_schema is set correctly

        # Prepare data using the shared model for the API call
        try:
            user_id_int = int(self.user_id)
            api_data = UserFactCreate(user_id=user_id_int, fact=fact)
            api_data_dict = api_data.model_dump()
        except ValueError:
            raise ToolError(
                message="Invalid User ID format. Expected an integer.",
                tool_name=self.name,
                error_code="INVALID_USER_ID_FORMAT",
            )
        except Exception as e:  # Catch potential model_dump errors
            raise ToolError(
                message=f"Error preparing data for API: {e}",
                tool_name=self.name,
                error_code="DATA_PREPARATION_ERROR",
            )

        logger.debug(
            f"Prepared data for /users/{{user_id}}/facts API: {api_data_dict}",
            extra=log_extra,
        )

        try:
            start_api_time = time.perf_counter()
            # Get the client using the lazy getter
            http_client = self.get_client()
            # Use the initialized client for the request
            response = await http_client.post(
                f"/api/users/{user_id_int}/facts",
                json=api_data_dict,  # Use http_client here
            )
            api_duration_ms = round((time.perf_counter() - start_api_time) * 1000)
            log_extra["api_duration_ms"] = api_duration_ms

            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

            duration_ms = round((time.perf_counter() - start_time) * 1000)
            log_extra["duration_ms"] = duration_ms
            logger.info(f"Successfully executed {self.name} tool", extra=log_extra)
            # Optionally return the ID of the created fact if the API returns it and it's useful
            # created_fact = response.json()
            # return f"Факт успешно добавлен. ID факта: {created_fact.get('id')}"
            return "Факт успешно добавлен."

        except httpx.HTTPStatusError as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000)
            log_extra["duration_ms"] = duration_ms
            log_extra["http_status"] = e.response.status_code
            log_extra["response_text"] = e.response.text
            logger.error(f"API call failed for {self.name}: {e}", extra=log_extra)
            raise ToolError(
                message=f"Ошибка API при добавлении факта ({e.response.status_code}): {e.response.text}",
                tool_name=self.name,
                error_code="API_ERROR",
            )
        except httpx.RequestError as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000)
            log_extra["duration_ms"] = duration_ms
            logger.error(
                f"Network error during {self.name} execution: {e}", extra=log_extra
            )
            raise ToolError(
                message=f"Сетевая ошибка при добавлении факта: {e}",
                tool_name=self.name,
                error_code="NETWORK_ERROR",
            )
        except Exception as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000)
            log_extra["duration_ms"] = duration_ms
            logger.exception(f"Unexpected error in {self.name}", extra=log_extra)
            raise ToolError(
                message=f"Непредвиденная ошибка при добавлении факта: {e}",
                tool_name=self.name,
                error_code="UNEXPECTED_ERROR",
            )
