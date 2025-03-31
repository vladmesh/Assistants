from datetime import datetime, timedelta, timezone
from typing import ClassVar, Optional, Type
from zoneinfo import ZoneInfo

import httpx
from config.logger import get_logger
from pydantic import BaseModel, Field
from tools.base import BaseTool
from utils.error_handler import ToolError

logger = get_logger(__name__)


class ReminderSchema(BaseModel):
    """Schema for reminder creation."""

    message: str = Field(..., description="Текст напоминания")
    delay_seconds: Optional[int] = Field(
        None,
        description=(
            "Через сколько секунд отправить напоминание (альтернатива datetime)"
        ),
    )
    datetime_str: Optional[str] = Field(
        None, description="Дата и время напоминания в формате ISO (YYYY-MM-DD HH:MM)"
    )
    timezone: Optional[str] = Field(
        None, description="Временная зона для datetime_str (например, 'Europe/Moscow')"
    )

    def validate_reminder_time(self) -> datetime:
        """Validate and convert input to UTC datetime"""
        if self.delay_seconds is not None and self.datetime_str is not None:
            raise ValueError(
                "Укажите либо delay_seconds, либо datetime_str с timezone, но не оба"
            )

        if self.delay_seconds is not None:
            if self.delay_seconds <= 0:
                raise ValueError("delay_seconds должен быть положительным числом")
            return datetime.now(timezone.utc) + timedelta(seconds=self.delay_seconds)

        if self.datetime_str is not None:
            if not self.timezone:
                raise ValueError(
                    "При указании datetime_str необходимо указать timezone"
                )
            try:
                local_tz = ZoneInfo(self.timezone)
                local_dt = datetime.fromisoformat(self.datetime_str)
                if local_dt.tzinfo is None:
                    local_dt = local_dt.replace(tzinfo=local_tz)
                return local_dt.astimezone(timezone.utc)
            except Exception as e:
                raise ValueError(f"Ошибка при обработке даты/времени: {str(e)}")

        raise ValueError(
            "Необходимо указать либо delay_seconds, либо datetime_str с timezone"
        )


class ReminderTool(BaseTool):
    NAME: ClassVar[str] = "reminder"
    DESCRIPTION: ClassVar[
        str
    ] = """Инструмент для создания напоминаний.
    Используйте его, когда пользователь просит напомнить о чем-то.

    Есть два способа указать время напоминания:
    1. delay_seconds - через сколько секунд отправить напоминание
    2. datetime_str + timezone - конкретные дата/время и часовой пояс

    Примеры использования:
    - "Напомни мне позвонить маме через 3600 секунд" (через час)
    - "Создай напоминание о встрече на 2024-03-15 15:00 Europe/Moscow"
    """

    name: str = NAME
    description: str = DESCRIPTION
    rest_service_url: str = "http://rest_service:8000"
    client: Optional[httpx.AsyncClient] = None
    args_schema: Type[BaseModel] = ReminderSchema

    def __init__(
        self,
        user_id: Optional[str] = None,
        rest_service_url: str = "http://rest_service:8000",
    ):
        super().__init__(
            name=self.NAME,
            description=self.DESCRIPTION,
            args_schema=ReminderSchema,
            user_id=user_id,
        )
        self.rest_service_url = rest_service_url
        self.client = httpx.AsyncClient(timeout=30.0)

    def _run(
        self,
        message: str,
        delay_seconds: Optional[int] = None,
        datetime_str: Optional[str] = None,
        timezone: Optional[str] = None,
    ) -> str:
        """Синхронный метод не используется"""
        raise NotImplementedError(
            "Этот инструмент поддерживает только асинхронные вызовы"
        )

    async def _execute(
        self,
        message: str,
        delay_seconds: Optional[int] = None,
        datetime_str: Optional[str] = None,
        timezone: Optional[str] = None,
    ) -> str:
        """Создает напоминание через REST API"""
        if not self.user_id:
            raise ToolError(
                message="User ID is required for creating reminders",
                tool_name=self.name,
                error_code="USER_ID_REQUIRED",
            )

        # Создаем и валидируем схему
        reminder_data = ReminderSchema(
            message=message,
            delay_seconds=delay_seconds,
            datetime_str=datetime_str,
            timezone=timezone,
        )

        try:
            # Получаем UTC datetime
            reminder_datetime = reminder_data.validate_reminder_time()

            logger.info(
                "Creating reminder",
                message=message,
                reminder_datetime=reminder_datetime.isoformat(),
                user_id=self.user_id,
            )

            # Создание CRON-выражения
            cron_expression = self._datetime_to_cron(reminder_datetime)

            # Получаем пользователя по telegram_id
            try:
                user_response = await self.client.get(
                    f"{self.rest_service_url}/api/users/",
                    params={"telegram_id": int(self.user_id)},
                )

                if user_response.status_code != 200:
                    logger.error(
                        "Failed to get user",
                        status_code=user_response.status_code,
                        response=user_response.text,
                    )
                    raise ToolError(
                        message="Пользователь не найден",
                        error_code="USER_NOT_FOUND",
                        details={"telegram_id": self.user_id},
                    )

                user_data = user_response.json()
                user_id = user_data["id"]
            except Exception as e:
                logger.error("Error getting user", error=str(e), exc_info=True)
                raise ToolError(
                    message="Ошибка при получении данных пользователя",
                    error_code="USER_FETCH_ERROR",
                    details={"error": str(e)},
                )

            # Подготовка данных для API
            data = {
                "name": message,
                "cron_expression": cron_expression,
                "type": "notification",
                "user_id": user_id,
            }

            try:
                # Отправка запроса к REST API
                response = await self.client.post(
                    f"{self.rest_service_url}/api/cronjobs/", json=data
                )

                if response.status_code not in [200, 201]:
                    logger.error(
                        "API request failed",
                        status_code=response.status_code,
                        response=response.text,
                    )
                    raise ToolError(
                        message="Ошибка при создании напоминания",
                        error_code="API_ERROR",
                        details={
                            "status_code": response.status_code,
                            "response": response.text,
                        },
                    )

                job_data = response.json()
                logger.info(
                    "Reminder created successfully",
                    job_id=job_data["id"],
                    message=message,
                )

                # Форматируем ответ в зависимости от типа входных данных
                if delay_seconds is not None:
                    return (
                        f"Напоминание создано: {message} (через {delay_seconds} секунд)"
                    )
                else:
                    local_time = reminder_datetime.astimezone(ZoneInfo(timezone))
                    return (
                        f"Напоминание создано: {message} на"
                        f" {local_time.strftime('%Y-%m-%d %H:%M %Z')}"
                    )

            except ToolError:
                raise
            except httpx.RequestError as e:
                logger.error("Request error", error=str(e))
                raise ToolError(
                    message="Ошибка при обращении к сервису напоминаний",
                    error_code="SERVICE_ERROR",
                    details={"error": str(e)},
                )
            except Exception as e:
                logger.error("Unknown error", error=str(e), exc_info=True)
                raise ToolError(
                    message="Неизвестная ошибка при создании напоминания",
                    error_code="UNKNOWN_ERROR",
                    details={"error": str(e)},
                )

        except ValueError as e:
            raise ToolError(
                message=str(e), tool_name=self.name, error_code="INVALID_INPUT"
            )

    def _datetime_to_cron(self, dt: datetime) -> str:
        """Преобразует datetime в CRON-выражение"""
        return f"{dt.minute} {dt.hour} {dt.day} {dt.month} *"
