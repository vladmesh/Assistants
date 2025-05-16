import json
import time  # Import time
from datetime import datetime, timezone as dt_timezone_class
from typing import Any, Optional, Type
from uuid import UUID  # Import UUID for reminder_id type hint in delete_reminder
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from config.logger import get_logger
from pydantic import BaseModel, Field, field_validator, model_validator

# Import RestServiceClient and specific schemas
from services.rest_service import RestServiceClient
from tools.base import BaseTool
from utils.error_handler import ToolError

from shared_models.api_schemas import ReminderCreate  # For ReminderCreateTool

logger = get_logger(__name__)


# --- Schemas for Reminder Tools ---


class ReminderCreateSchema(BaseModel):
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
        description="Временная зона. Для 'one_time' напоминаний (где используется trigger_at) это поле обязательно. "
                    "Для 'recurring' напоминаний (где используется cron_expression) это поле опционально в случае, если час не указан в CRON выражении; "
                    "Если указываешь час в CRON выражении, то timezone нужен обязательно.",
    )
    cron_expression: Optional[str] = Field(
        None,
        description="CRON-выражение для 'recurring' напоминания (например, '0 10 * * *').",
    )

    @field_validator("payload")
    @classmethod
    def validate_payload_is_json(cls, v: str) -> str:
        try:
            json.loads(v)
            return v
        except json.JSONDecodeError:
            raise ValueError("payload должен быть валидной JSON строкой")

    @model_validator(mode="before")
    @classmethod
    def check_trigger_conditions(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        reminder_type = data.get("type")
        trigger_at = data.get("trigger_at")
        timezone_val = data.get("timezone")
        cron_expression = data.get("cron_expression")

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
            if trigger_at:
                raise ValueError(
                    "Для 'recurring' напоминания не должен быть указан trigger_at."
                )
        elif reminder_type is not None:
            raise ValueError("type должен быть 'one_time' или 'recurring'")
        # Removed the more complex elif as 'type' is mandatory for create schema

        return data

    def get_trigger_datetime_utc(self) -> Optional[datetime]:
        """Convert trigger_at with timezone to UTC datetime."""
        if self.type == "one_time" and self.trigger_at and self.timezone:
            try:
                local_tz = ZoneInfo(self.timezone)
                try:
                    local_dt = datetime.fromisoformat(self.trigger_at)
                except ValueError:
                    local_dt = datetime.strptime(self.trigger_at, "%Y-%m-%d %H:%M")

                if local_dt.tzinfo is None:
                    local_dt = local_dt.replace(tzinfo=local_tz)
                return local_dt.astimezone(dt_timezone_class.utc)
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


class ReminderListSchema(BaseModel):
    """Schema for listing active reminders. No arguments needed for now."""

    pass


class ReminderDeleteSchema(BaseModel):
    """Schema for deleting a reminder."""

    reminder_id: UUID = Field(
        ..., description="ID напоминания (UUID), которое нужно удалить."
    )


# --- Base Class for Reminder Tools ---
class BaseReminderTool(BaseTool):
    """Base class for Reminder tools."""

    # rest_service_url is inherited from BaseTool if settings provides it, or can be set here.
    # For clarity, let tools use settings.REST_SERVICE_URL via RestServiceClient
    # _client: Optional[httpx.AsyncClient] = None # Not needed if using RestServiceClient
    _rest_client: Optional[RestServiceClient] = None

    def get_rest_client(self) -> RestServiceClient:
        """Lazily initialize and return the RestServiceClient."""
        if self._rest_client is None:
            # self.settings should be available from BaseTool if passed by ToolFactory
            base_url = (
                self.settings.REST_SERVICE_URL
                if self.settings
                else "http://rest_service:8000"
            )
            self._rest_client = RestServiceClient(base_url=base_url)
        return self._rest_client

    # _handle_api_error and _ensure_ids_present can be removed if RestServiceClient handles this
    # For now, keeping _ensure_ids_present as it's tool-specific logic regarding assistant_id
    def _ensure_ids_present(self) -> None:
        """Ensures user_id is present. Assistant_id check is optional for some tools."""
        if not self.user_id:
            raise ToolError(
                message="User ID is required for this tool.",
                tool_name=self.name,
                error_code="USER_ID_REQUIRED",
            )
        # assistant_id is not strictly required for list/delete by user, but useful for logging.
        # if not self.assistant_id: # Example if we wanted to make it mandatory for some base tools
        #     raise ToolError(
        #         message="Assistant ID is required for this tool.",
        #         tool_name=self.name,
        #         error_code="ASSISTANT_ID_REQUIRED",
        #     )


# --- Concrete Reminder Tools ---


class ReminderCreateTool(BaseReminderTool):
    """Инструмент для создания напоминаний."""

    args_schema: Type[ReminderCreateSchema] = ReminderCreateSchema

    async def _execute(
        self,
        type: str,
        payload: str,
        trigger_at: Optional[str] = None,
        timezone: Optional[str] = None,
        cron_expression: Optional[str] = None,
    ) -> str:
        """Создает напоминание через RestServiceClient."""
        start_time = time.perf_counter()
        log_extra = {
            "tool_name": self.name,
            "user_id": self.user_id,
            "assistant_id": self.assistant_id,
            "action": "create_reminder",
        }
        self._ensure_ids_present()

        try:
            reminder_input_schema = ReminderCreateSchema(
                type=type,
                payload=payload,
                trigger_at=trigger_at,
                timezone=timezone,
                cron_expression=cron_expression,
            )
        except ValueError as e:
            log_extra["validation_error"] = str(e)
            duration_ms = round((time.perf_counter() - start_time) * 1000)
            log_extra["duration_ms"] = duration_ms
            logger.warning(f"Input validation failed for {self.name}", extra=log_extra)
            raise ToolError(
                message=f"Ошибка валидации: {str(e)}",
                tool_name=self.name,
                error_code="INVALID_INPUT",
            )

        trigger_datetime_utc_iso = None
        final_cron_expression = reminder_input_schema.cron_expression

        if reminder_input_schema.type == "one_time":
            if not reminder_input_schema.trigger_at or not reminder_input_schema.timezone:
                raise ToolError(
                    message="Для 'one_time' напоминания необходимо указать trigger_at и timezone.",
                    tool_name=self.name,
                    error_code="INVALID_INPUT",
                )
            dt_utc = reminder_input_schema.get_trigger_datetime_utc()
            if dt_utc:
                trigger_datetime_utc_iso = dt_utc.isoformat()
            final_cron_expression = None

        elif reminder_input_schema.type == "recurring" and reminder_input_schema.cron_expression and reminder_input_schema.timezone:
            try:
                cron_parts = reminder_input_schema.cron_expression.split()
                if len(cron_parts) == 5:
                    minute_cron, hour_cron, day_month_cron, month_cron, day_week_cron = cron_parts
                    
                    if hour_cron.isdigit():
                        local_hour = int(hour_cron)
                        if not (0 <= local_hour <= 23):
                            logger.warning(
                                f"Час в CRON '{local_hour}' вне диапазона 0-23. "
                                f"Используется оригинальное CRON выражение: '{reminder_input_schema.cron_expression}'.",
                                extra=log_extra
                            )
                        else:
                            context_minute_for_conversion = 0
                            if minute_cron.isdigit():
                                context_minute_for_conversion = int(minute_cron)
                                if not (0 <= context_minute_for_conversion <= 59):
                                     context_minute_for_conversion = 0
                            
                            now_in_user_tz = datetime.now(ZoneInfo(reminder_input_schema.timezone))
                            local_dt_for_conversion = now_in_user_tz.replace(
                                hour=local_hour, minute=context_minute_for_conversion, second=0, microsecond=0
                            )
                            
                            utc_dt = local_dt_for_conversion.astimezone(dt_timezone_class.utc)
                            utc_hour = utc_dt.hour
                            
                            final_cron_expression = f"{minute_cron} {utc_hour} {day_month_cron} {month_cron} {day_week_cron}"
                            log_extra["original_cron"] = reminder_input_schema.cron_expression
                            log_extra["converted_cron"] = final_cron_expression
                            log_extra["conversion_timezone"] = reminder_input_schema.timezone
                            logger.info(
                                f"Конвертировано CRON выражение с учетом timezone. "
                                f"Оригинал: '{reminder_input_schema.cron_expression}' ({reminder_input_schema.timezone}), "
                                f"Результат (UTC): '{final_cron_expression}'.",
                                extra=log_extra
                            )
                    else:
                        logger.warning(
                            f"Час '{hour_cron}' в CRON выражении '{reminder_input_schema.cron_expression}' не является простой цифрой. "
                            f"Конвертация в UTC не выполнена. Используется оригинальное выражение.",
                            extra=log_extra
                        )
                else:
                    logger.warning(
                        f"CRON выражение '{reminder_input_schema.cron_expression}' имеет неверный формат (не 5 частей). "
                        f"Конвертация в UTC не выполнена. Используется оригинальное выражение.",
                        extra=log_extra
                    )
            except ZoneInfoNotFoundError:
                 logger.warning(
                    f"Неверная временная зона '{reminder_input_schema.timezone}' указана для CRON выражения "
                    f"'{reminder_input_schema.cron_expression}'. Используется оригинальное выражение.",
                    extra=log_extra
                 )            
            except ValueError as ve:
                 logger.warning(
                    f"Ошибка значения при попытке конвертировать CRON выражение '{reminder_input_schema.cron_expression}' "
                    f"с timezone '{reminder_input_schema.timezone}': {str(ve)}. "
                    f"Используется оригинальное выражение.",
                    extra=log_extra
                )
            except Exception as e: 
                logger.exception(
                    f"Непредвиденная ошибка при конвертации CRON выражения '{reminder_input_schema.cron_expression}' "
                    f"с timezone '{reminder_input_schema.timezone}': {str(e)}. "
                    f"Используется оригинальное выражение.",
                    exc_info=True, 
                    extra=log_extra
                )
        elif reminder_input_schema.type == "recurring":
            trigger_datetime_utc_iso = None

        # Prepare ReminderCreate Pydantic model for the client
        reminder_create_data = ReminderCreate(
            user_id=int(self.user_id),  # API model expects int
            assistant_id=str(self.assistant_id),  # API model expects UUID as str
            type=reminder_input_schema.type,
            payload=reminder_input_schema.payload,
            status="active",  # Default status
            trigger_at=trigger_datetime_utc_iso, 
            cron_expression=final_cron_expression,
        )

        rest_client = self.get_rest_client()
        try:
            created_reminder = await rest_client.create_reminder(reminder_create_data)
            duration_ms = round((time.perf_counter() - start_time) * 1000)
            log_extra["duration_ms"] = duration_ms

            if created_reminder:
                log_extra["reminder_id"] = str(created_reminder.id)
                logger.info(
                    "Reminder successfully created via RestServiceClient",
                    extra=log_extra,
                )
                return "Напоминание успешно создано."
            else:
                logger.error(
                    "Reminder creation failed, RestServiceClient returned None",
                    extra=log_extra,
                )
                raise ToolError(
                    message="Не удалось создать напоминание.",
                    tool_name=self.name,
                    error_code="API_ERROR",
                )

        except ToolError:  # Re-raise ToolErrors directly
            raise
        except Exception as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000)
            log_extra["duration_ms"] = duration_ms
            log_extra["unexpected_error"] = str(e)
            logger.exception(
                "Unexpected error during reminder creation via RestServiceClient",
                exc_info=True,
                extra=log_extra,
            )
            raise ToolError(
                message=f"Непредвиденная ошибка: {str(e)}",
                tool_name=self.name,
                error_code="UNEXPECTED_ERROR",
            )


class ReminderListTool(BaseReminderTool):
    """Инструмент для получения списка активных напоминаний пользователя."""

    args_schema: Type[ReminderListSchema] = ReminderListSchema

    async def _execute(self) -> str:
        """Получает список активных напоминаний через RestServiceClient."""
        start_time = time.perf_counter()
        log_extra = {
            "tool_name": self.name,
            "user_id": self.user_id,
            "assistant_id": self.assistant_id,
            "action": "list_reminders",
        }
        self._ensure_ids_present()

        if not self.user_id:  # Should be caught by _ensure_ids_present
            return "Ошибка: ID пользователя не найден."

        rest_client = self.get_rest_client()
        try:
            reminders = await rest_client.get_user_active_reminders(
                user_id=int(self.user_id)
            )
            duration_ms = round((time.perf_counter() - start_time) * 1000)
            log_extra["duration_ms"] = duration_ms
            log_extra["reminders_count"] = len(reminders)
            logger.info(
                "Successfully fetched active reminders via RestServiceClient",
                extra=log_extra,
            )

            if not reminders:
                return "У вас нет активных напоминаний."

            formatted_reminders = []
            for r in reminders:
                payload_summary = ""
                payload_dict = None

                if isinstance(r.payload, dict):
                    payload_dict = r.payload
                elif isinstance(r.payload, str):
                    try:
                        payload_dict = json.loads(r.payload)
                    except json.JSONDecodeError:
                        payload_summary = (
                            r.payload[:50] + "..." if len(r.payload) > 50 else r.payload
                        )
                        logger.warning(
                            f"Reminder payload is a string but not valid JSON: {r.payload[:100]}",
                            tool_name=self.name,
                            reminder_id=str(r.id),
                        )
                else:
                    # Handle other unexpected types for payload if necessary
                    payload_summary = (
                        str(r.payload)[:50] + "..."
                        if len(str(r.payload)) > 50
                        else str(r.payload)
                    )
                    logger.warning(
                        f"Reminder payload has unexpected type: {type(r.payload)}",
                        tool_name=self.name,
                        reminder_id=str(r.id),
                    )

                if payload_dict:
                    payload_text = payload_dict.get(
                        "text", payload_dict.get("message", str(payload_dict))
                    )
                    payload_summary = (
                        payload_text[:50] + "..."
                        if len(payload_text) > 50
                        else payload_text
                    )
                elif (
                    not payload_summary
                ):  # If payload_summary wasn't set above (e.g. not string, not dict, not parsable)
                    payload_summary = "(не удалось отобразить содержимое)"

                trigger_info = ""
                if r.type == "one_time" and r.trigger_at:
                    try:
                        # Ensure trigger_at is datetime before formatting
                        dt_obj = (
                            r.trigger_at
                            if isinstance(r.trigger_at, datetime)
                            else datetime.fromisoformat(
                                str(r.trigger_at).replace("Z", "+00:00")
                            )
                        )
                        trigger_info = (
                            f"Однократно: {dt_obj.strftime('%Y-%m-%d %H:%M:%S %Z')}"
                        )
                    except ValueError:
                        trigger_info = f"Однократно: {str(r.trigger_at)} (не удалось распарсить дату)"
                elif r.type == "recurring" and r.cron_expression:
                    trigger_info = f"Повторяющееся: {r.cron_expression}"

                reminder_id_str = str(r.id)  # Display UUID as string
                formatted_reminders.append(
                    f"ID: {reminder_id_str} - «{payload_summary}» ({trigger_info})"
                )

            return "Ваши активные напоминания:\n" + "\n".join(formatted_reminders)

        except ToolError:  # Re-raise ToolErrors directly
            raise
        except Exception as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000)
            log_extra["duration_ms"] = duration_ms
            log_extra["unexpected_error"] = str(e)
            logger.exception(
                "Unexpected error during listing reminders via RestServiceClient",
                exc_info=True,
                extra=log_extra,
            )
            raise ToolError(
                message=f"Непредвиденная ошибка: {str(e)}",
                tool_name=self.name,
                error_code="UNEXPECTED_ERROR",
            )


class ReminderDeleteTool(BaseReminderTool):
    """Инструмент для удаления напоминания по ID."""

    args_schema: Type[ReminderDeleteSchema] = ReminderDeleteSchema

    async def _execute(self, reminder_id: UUID) -> str:
        """Удаляет напоминание по ID через RestServiceClient."""
        start_time = time.perf_counter()
        log_extra = {
            "tool_name": self.name,
            "user_id": self.user_id,
            "assistant_id": self.assistant_id,
            "reminder_id_to_delete": str(reminder_id),
            "action": "delete_reminder",
        }
        self._ensure_ids_present()

        rest_client = self.get_rest_client()
        try:
            success = await rest_client.delete_reminder(reminder_id=reminder_id)
            duration_ms = round((time.perf_counter() - start_time) * 1000)
            log_extra["duration_ms"] = duration_ms

            if success:
                logger.info(
                    f"Reminder {reminder_id} successfully deleted via RestServiceClient",
                    extra=log_extra,
                )
                return f"Напоминание с ID {reminder_id} успешно удалено."
            else:
                # RestServiceClient.delete_reminder logs error and returns False.
                # ToolError might have been raised by RestServiceClient if it were configured to do so for HTTP errors.
                # For now, assume False means a non-exception failure reported by the client.
                logger.warning(
                    f"Deletion of reminder {reminder_id} reported as failed by RestServiceClient",
                    extra=log_extra,
                )
                raise ToolError(
                    message=f"Не удалось удалить напоминание с ID {reminder_id}.",
                    tool_name=self.name,
                    error_code="API_ERROR",
                )

        except ToolError:  # Re-raise ToolErrors directly
            raise
        except Exception as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000)
            log_extra["duration_ms"] = duration_ms
            log_extra["unexpected_error"] = str(e)
            logger.exception(
                "Unexpected error during reminder deletion via RestServiceClient",
                exc_info=True,
                extra=log_extra,
            )
            raise ToolError(
                message=f"Непредвиденная ошибка: {str(e)}",
                tool_name=self.name,
                error_code="UNEXPECTED_ERROR",
            )
