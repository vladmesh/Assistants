import json
from datetime import datetime, timezone
from typing import Optional, Type
from zoneinfo import ZoneInfo

import httpx
from config.logger import get_logger
from pydantic import BaseModel, Field, root_validator, validator
from tools.base import BaseTool
from utils.error_handler import ToolError

logger = get_logger(__name__)


class ReminderSchema(BaseModel):
    """Schema for reminder creation input validation."""

    type: str = Field(..., description="Тип напоминания: 'one_time' или 'recurring'")
    payload: str = Field(
        ..., description="Содержимое напоминания в формате JSON-строки"
    )
    trigger_at: Optional[str] = Field(
        None,
        description="Дата и время для 'one_time' напоминания в формате ISO (YYYY-MM-DD HH:MM). Обязательно вместе с timezone.",
    )
    timezone: Optional[str] = Field(
        None,
        description="Временная зона для trigger_at (например, 'Europe/Moscow'). Обязательно для 'one_time'.",
    )
    cron_expression: Optional[str] = Field(
        None,
        description="CRON-выражение для 'recurring' напоминания (например, '0 10 * * *').",
    )

    @validator("payload")
    def validate_payload_is_json(cls, v):
        try:
            json.loads(v)
            return v
        except json.JSONDecodeError:
            raise ValueError("payload должен быть валидной JSON строкой")

    @root_validator(pre=True)
    def check_trigger_conditions(cls, values):
        reminder_type = values.get("type")
        trigger_at = values.get("trigger_at")
        timezone_val = values.get("timezone")
        cron_expression = values.get("cron_expression")

        if reminder_type == "one_time":
            if not trigger_at or not timezone_val:
                raise ValueError(
                    "Для 'one_time' напоминания необходимо указать trigger_at и timezone."
                )
            if cron_expression:
                raise ValueError(
                    "Для 'one_time' напоминания не должен быть указан cron_expression."
                )
        elif reminder_type == "recurring":
            if not cron_expression:
                raise ValueError(
                    "Для 'recurring' напоминания необходимо указать cron_expression."
                )
            if trigger_at or timezone_val:
                raise ValueError(
                    "Для 'recurring' напоминания не должны быть указаны trigger_at или timezone."
                )
        else:
            raise ValueError("type должен быть 'one_time' или 'recurring'")

        return values

    def get_trigger_datetime_utc(self) -> Optional[datetime]:
        """Convert trigger_at with timezone to UTC datetime."""
        if self.type == "one_time" and self.trigger_at and self.timezone:
            try:
                local_tz = ZoneInfo(self.timezone)
                # Attempt to parse with or without seconds/microseconds
                try:
                    local_dt = datetime.fromisoformat(self.trigger_at)
                except ValueError:
                    # Try parsing without seconds if fromisoformat fails initially
                    local_dt = datetime.strptime(self.trigger_at, "%Y-%m-%d %H:%M")

                if local_dt.tzinfo is None:
                    local_dt = local_dt.replace(tzinfo=local_tz)
                return local_dt.astimezone(timezone.utc)
            except ValueError as e:
                logger.error(f"Invalid datetime format: {self.trigger_at}. Error: {e}")
                raise ValueError(
                    f"Неверный формат даты/времени для trigger_at: '{self.trigger_at}'. Ожидается YYYY-MM-DD HH:MM."
                )
            except Exception as e:
                logger.error(f"Error processing datetime/timezone: {e}")
                raise ValueError(
                    f"Ошибка при обработке даты/времени/таймзоны: {str(e)}"
                )
        return None


class ReminderTool(BaseTool):
    """Инструмент для создания напоминаний. Использует значения name и description из базы данных."""

    # Restore the Type annotation
    args_schema: Type[ReminderSchema] = ReminderSchema

    # Keep specific attributes
    rest_service_url: str = "http://rest_service:8000"
    _client: Optional[httpx.AsyncClient] = None  # For lazy init

    def get_client(self) -> httpx.AsyncClient:
        """Lazily initialize and return the httpx client."""
        if self._client is None:
            # Consider adding timeout configuration from settings if available
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _execute(
        self,
        type: str,
        payload: str,
        trigger_at: Optional[str] = None,
        timezone: Optional[str] = None,
        cron_expression: Optional[str] = None,
    ) -> str:
        """Создает напоминание через REST API /reminders/"""
        # Access attributes like user_id and assistant_id from self (set by BaseTool)
        if not self.user_id:
            raise ToolError(
                message="User ID is required",
                tool_name=self.name,
                error_code="USER_ID_REQUIRED",
            )
        if not self.assistant_id:
            raise ToolError(
                message="Assistant ID is required",
                tool_name=self.name,
                error_code="ASSISTANT_ID_REQUIRED",
            )

        # Validate input using the schema
        try:
            reminder_input = ReminderSchema(
                type=type,
                payload=payload,
                trigger_at=trigger_at,
                timezone=timezone,
                cron_expression=cron_expression,
            )
        except ValueError as e:
            raise ToolError(
                message=f"Ошибка валидации входных данных: {str(e)}",
                tool_name=self.name,
                error_code="INVALID_INPUT",
            )

        # Prepare data for the API call using the shared model structure
        trigger_datetime_utc = reminder_input.get_trigger_datetime_utc()
        api_data: dict = {
            "user_id": int(self.user_id),  # API expects int
            "assistant_id": str(self.assistant_id),  # API expects str UUID
            "type": reminder_input.type,
            "payload": reminder_input.payload,
            "status": "active",
        }
        if reminder_input.type == "one_time" and trigger_datetime_utc:
            api_data["trigger_at"] = trigger_datetime_utc.isoformat()
        elif reminder_input.type == "recurring" and reminder_input.cron_expression:
            api_data["cron_expression"] = reminder_input.cron_expression

        logger.debug("Prepared data for /reminders API", data=api_data)
        http_client = self.get_client()  # Use lazy getter

        try:
            response = await http_client.post(
                f"{self.rest_service_url}/api/reminders/", json=api_data
            )
            if response.status_code not in [200, 201]:
                logger.error(
                    "Reminder API request failed",
                    status_code=response.status_code,
                    response=response.text,
                )
                error_detail = response.text
                try:
                    detail_json = response.json()
                    error_detail = detail_json.get("detail", error_detail)
                except Exception:
                    pass
                raise ToolError(
                    message=f"Ошибка API ({response.status_code}): {error_detail}",
                    tool_name=self.name,
                    error_code="API_ERROR",
                )

            logger.info("Reminder successfully created via API")
            return "Напоминание успешно создано."

        except httpx.RequestError as e:
            logger.error(f"HTTP request failed: {e}", exc_info=True)
            raise ToolError(
                message=f"Ошибка сети при создании напоминания: {str(e)}",
                tool_name=self.name,
                error_code="NETWORK_ERROR",
            )
        except Exception as e:
            logger.exception("Unexpected error during reminder creation", exc_info=True)
            raise ToolError(
                message=f"Непредвиденная ошибка: {str(e)}",
                tool_name=self.name,
                error_code="UNEXPECTED_ERROR",
            )

    # Remove the old _datetime_to_cron method as it's no longer needed here
    # def _datetime_to_cron(self, dt: datetime) -> str:
    #     """Преобразует datetime в CRON-выражение"""
    #     return f"{dt.minute} {dt.hour} {dt.day} {dt.month} *"
