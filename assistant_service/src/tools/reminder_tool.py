import json
from datetime import datetime, timezone
from typing import ClassVar, Optional, Type
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx
from config.logger import get_logger
from pydantic import BaseModel, Field, root_validator, validator
from tools.base import BaseTool
from utils.error_handler import ToolError

logger = get_logger(__name__)


class ReminderSchema(BaseModel):
    """Schema for reminder creation using the new API."""

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
    NAME: ClassVar[str] = "create_reminder"  # Changed name to be more descriptive
    DESCRIPTION: ClassVar[
        str
    ] = """Инструмент для создания одноразовых или повторяющихся напоминаний.
    Используйте его, когда пользователь просит напомнить о чем-то.

    Укажите тип напоминания ('one_time' или 'recurring').
    - Для 'one_time': укажите 'trigger_at' (YYYY-MM-DD HH:MM) и 'timezone' (например, 'Europe/Moscow').
    - Для 'recurring': укажите 'cron_expression' (например, '0 10 * * *' для "каждый день в 10:00").
    - Всегда указывайте 'payload' - JSON-строку с деталями для напоминания (например, '{"text": "Позвонить маме"}').

    Примеры использования:
    - Создать напоминание: тип 'one_time', время '2024-07-15 15:30', зона 'Europe/Moscow', payload '{"text": "Встреча с командой"}'
    - Создать ежедневное напоминание: тип 'recurring', cron '0 9 * * *', payload '{"action": "check_emails"}'
    """

    name: str = NAME
    description: str = DESCRIPTION
    rest_service_url: str = "http://rest_service:8000"
    client: Optional[httpx.AsyncClient] = None
    args_schema: Type[BaseModel] = ReminderSchema
    assistant_id: Optional[UUID] = None  # Add field to store assistant ID

    def __init__(
        self,
        user_id: Optional[str] = None,
        assistant_id: Optional[UUID] = None,  # Receive assistant_id
        rest_service_url: str = "http://rest_service:8000",
    ):
        super().__init__(
            name=self.NAME,
            description=self.DESCRIPTION,
            args_schema=ReminderSchema,
            user_id=user_id,
        )
        self.assistant_id = assistant_id  # Store assistant_id
        self.rest_service_url = rest_service_url
        self.client = httpx.AsyncClient(timeout=30.0)

    def _run(self, *args, **kwargs) -> str:
        """Синхронный метод не используется"""
        raise NotImplementedError(
            "Этот инструмент поддерживает только асинхронные вызовы"
        )

    async def _execute(
        self,
        type: str,
        payload: str,
        trigger_at: Optional[str] = None,
        timezone: Optional[str] = None,
        cron_expression: Optional[str] = None,
    ) -> str:
        """Создает напоминание через новый REST API /reminders/"""
        if not self.user_id:
            raise ToolError(
                message="User ID is required for creating reminders",
                tool_name=self.name,
                error_code="USER_ID_REQUIRED",
            )

        if not self.assistant_id:
            raise ToolError(
                message="Assistant ID is required for creating reminders",
                tool_name=self.name,
                error_code="ASSISTANT_ID_REQUIRED",
            )

        # Создаем и валидируем схему
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

        try:
            # Получаем UTC datetime для one_time напоминаний
            trigger_datetime_utc = reminder_input.get_trigger_datetime_utc()

            logger.info(
                "Attempting to create reminder",
                type=reminder_input.type,
                trigger_at_utc=(
                    trigger_datetime_utc.isoformat() if trigger_datetime_utc else None
                ),
                cron=reminder_input.cron_expression,
                payload=reminder_input.payload,
                user_id=self.user_id,  # This is telegram_id
                assistant_id=self.assistant_id,
            )

            # Получаем пользователя (database ID) по telegram_id - ЭТО БОЛЬШЕ НЕ НУЖНО!
            # self.user_id УЖЕ является ID из базы данных
            user_db_id = None
            try:
                # Convert self.user_id (assumed to be DB ID string) to int
                user_db_id = int(self.user_id)
                logger.info(f"Using provided user DB ID: {user_db_id}")
                # Verify user exists? Maybe not necessary if ID comes from validated source

            except (ValueError, TypeError):
                logger.error(
                    "Invalid user_id format (expected int convertible string)",
                    user_id=self.user_id,
                )
                raise ToolError(
                    message="Неверный формат ID пользователя.",
                    error_code="INVALID_USER_ID_FORMAT",
                )

            # Подготовка данных для API /reminders/
            api_data = {
                "user_id": user_db_id,  # Use database ID directly
                "assistant_id": str(
                    self.assistant_id
                ),  # Ensure UUID is string for JSON
                "type": reminder_input.type,
                "payload": reminder_input.payload,
                "status": "active",  # Default to active? Or should API handle this? Let's set it.
            }
            if reminder_input.type == "one_time" and trigger_datetime_utc:
                # API expects ISO format string for datetime
                api_data["trigger_at"] = trigger_datetime_utc.isoformat()
            elif reminder_input.type == "recurring" and reminder_input.cron_expression:
                api_data["cron_expression"] = reminder_input.cron_expression

            logger.debug("Prepared data for /reminders API", data=api_data)

            try:
                # Отправка запроса к REST API /reminders/
                response = await self.client.post(
                    f"{self.rest_service_url}/api/reminders/", json=api_data
                )

                if response.status_code not in [200, 201]:
                    logger.error(
                        "Reminder API request failed",
                        status_code=response.status_code,
                        response=response.text,
                        request_data=api_data,
                    )
                    raise ToolError(
                        message="Ошибка при создании напоминания через API.",
                        error_code="REMINDER_API_ERROR",
                        details={
                            "status_code": response.status_code,
                            "response": response.text,
                        },
                    )

                reminder_response_data = response.json()
                logger.info(
                    "Reminder created successfully via API",
                    reminder_id=reminder_response_data["id"],
                    type=reminder_input.type,
                )

                # Формируем ответ пользователю
                if reminder_input.type == "one_time":
                    # Show local time back to user
                    local_time_str = "не указано"
                    if trigger_datetime_utc and reminder_input.timezone:
                        try:
                            local_tz = ZoneInfo(reminder_input.timezone)
                            local_dt = trigger_datetime_utc.astimezone(local_tz)
                            local_time_str = local_dt.strftime("%Y-%m-%d %H:%M %Z")
                        except Exception:
                            local_time_str = trigger_datetime_utc.strftime(
                                "%Y-%m-%d %H:%M UTC"
                            )  # Fallback to UTC

                    return (
                        f"Одноразовое напоминание создано на {local_time_str}. "
                        f"Содержание: {reminder_input.payload}"  # Maybe summarize payload?
                    )
                else:  # recurring
                    return (
                        f"Повторяющееся напоминание создано с правилом '{reminder_input.cron_expression}'. "
                        f"Содержание: {reminder_input.payload}"
                    )

            except ToolError:
                raise  # Re-raise specific tool errors
            except httpx.RequestError as e:
                logger.error(
                    "Reminder API request error", error=str(e), request_data=api_data
                )
                raise ToolError(
                    message="Ошибка при обращении к сервису напоминаний (сетевая проблема).",
                    error_code="REMINDER_API_NETWORK_ERROR",
                    details={"error": str(e)},
                )
            except Exception as e:
                logger.error(
                    "Unknown error during reminder creation API call",
                    error=str(e),
                    exc_info=True,
                )
                raise ToolError(
                    message="Неизвестная ошибка при создании напоминания.",
                    error_code="REMINDER_API_UNKNOWN_ERROR",
                    details={"error": str(e)},
                )

        except (
            ValueError
        ) as e:  # Catches validation errors from ReminderSchema or get_trigger_datetime_utc
            logger.error("Input validation failed", error=str(e))
            raise ToolError(
                message=f"Ошибка входных данных: {str(e)}",
                tool_name=self.name,
                error_code="INVALID_INPUT",
            )
        except ToolError:
            raise  # Re-raise ToolErrors from user fetching etc.
        except Exception as e:
            logger.error("Unexpected error in _execute", error=str(e), exc_info=True)
            raise ToolError(
                message=f"Непредвиденная ошибка: {str(e)}",
                tool_name=self.name,
                error_code="TOOL_UNEXPECTED_ERROR",
            )

    # Remove the old _datetime_to_cron method as it's no longer needed here
    # def _datetime_to_cron(self, dt: datetime) -> str:
    #     """Преобразует datetime в CRON-выражение"""
    #     return f"{dt.minute} {dt.hour} {dt.day} {dt.month} *"
