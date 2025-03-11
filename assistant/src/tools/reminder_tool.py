from typing import Optional, Type, ClassVar
from datetime import datetime, timezone
from tools.base import BaseTool
import httpx
from config.logger import get_logger
from utils.error_handler import ToolError
from pydantic import BaseModel, Field

logger = get_logger(__name__)

class ReminderSchema(BaseModel):
    """Schema for reminder creation."""
    message: str = Field(..., description="Текст напоминания")
    datetime_str: str = Field(..., description="Дата и время напоминания в формате ISO (YYYY-MM-DD HH:MM) в UTC времени") 
    

class ReminderTool(BaseTool):
    NAME: ClassVar[str] = "reminder"
    DESCRIPTION: ClassVar[str] = """Инструмент для создания напоминаний.
    Используйте его, когда пользователь просит напомнить о чем-то в определенное время.
    Он принимает дату и время СТРОГО в UTC времени. Если пользователь указывает время в своем часовом поясе, 
    то нужно будет вычислить, какое это будет время в UTC.
    
    Примеры использования:
    - "Напомни мне позвонить маме завтра в 15:00"
    - "Создай напоминание о встрече через 2 часа"
    - "Напомни мне о дедлайне через 3 дня в 18:00"
    
    Параметры:
    - message: Текст напоминания
    - datetime_str: Дата и время напоминания в формате ISO (YYYY-MM-DD HH:MM) в UTC времени
    """
    
    name: str = NAME
    description: str = DESCRIPTION
    rest_service_url: str = "http://rest_service:8000"
    client: Optional[httpx.AsyncClient] = None
    args_schema: Type[BaseModel] = ReminderSchema
    
    def __init__(self, user_id: Optional[str] = None, rest_service_url: str = "http://rest_service:8000"):
        super().__init__(
            name=self.NAME,
            description=self.DESCRIPTION,
            args_schema=ReminderSchema,
            user_id=user_id
        )
        self.rest_service_url = rest_service_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    def _run(self, message: str, datetime_str: str) -> str:
        """Синхронный метод не используется"""
        raise NotImplementedError("Этот инструмент поддерживает только асинхронные вызовы")
    
    async def _execute(self, message: str, datetime_str: str) -> str:
        """Создает напоминание через REST API"""
        if not self.user_id:
            raise ToolError(
                message="User ID is required for creating reminders",
                tool_name=self.name,
                error_code="USER_ID_REQUIRED"
            )

        logger.info("Starting reminder creation",
                   message=message,
                   datetime_str=datetime_str,
                   user_id=self.user_id,
                   current_time=datetime.now(timezone.utc).isoformat())
        
        # Парсинг даты и времени
        try:
            logger.info("Parsing datetime",
                       datetime_str=datetime_str,
                       current_time=datetime.now(timezone.utc).isoformat())
            
            # Преобразуем строку в datetime и добавляем UTC timezone если его нет
            reminder_datetime = datetime.fromisoformat(datetime_str)
            if reminder_datetime.tzinfo is None:
                reminder_datetime = reminder_datetime.replace(tzinfo=timezone.utc)
            
            logger.info("Parsed datetime",
                       reminder_datetime=reminder_datetime.isoformat(),
                       current_time=datetime.now(timezone.utc).isoformat(),
                       is_past=reminder_datetime < datetime.now(timezone.utc))
            
            if reminder_datetime < datetime.now(timezone.utc):
                raise ToolError(
                    message="Дата напоминания не может быть в прошлом",
                    tool_name=self.name,
                    error_code="INVALID_DATETIME",
                    details={"datetime": datetime_str}
                )
        except ValueError as e:
            logger.error("Failed to parse datetime",
                        datetime_str=datetime_str,
                        error=str(e))
            raise ToolError(
                message="Неверный формат даты и времени",
                tool_name=self.name,
                error_code="INVALID_DATETIME_FORMAT",
                details={"datetime": datetime_str, "error": str(e)}
            )
        
        # Создание CRON-выражения
        cron_expression = self._datetime_to_cron(reminder_datetime)
        
        # Получаем пользователя по telegram_id
        try:
            user_response = await self.client.get(
                f"{self.rest_service_url}/api/users/",
                params={"telegram_id": int(self.user_id)}
            )
            
            if user_response.status_code != 200:
                logger.error("Failed to get user",
                           status_code=user_response.status_code,
                           response=user_response.text)
                raise ToolError(
                    message="Пользователь не найден",
                    error_code="USER_NOT_FOUND",
                    details={"telegram_id": self.user_id}
                )
            
            user_data = user_response.json()
            user_id = user_data["id"]
        except Exception as e:
            logger.error("Error getting user",
                        error=str(e),
                        exc_info=True)
            raise ToolError(
                message="Ошибка при получении данных пользователя",
                error_code="USER_FETCH_ERROR",
                details={"error": str(e)}
            )
        
        # Подготовка данных для API
        data = {
            "name": message,
            "cron_expression": cron_expression,
            "type": "notification",
            "user_id": user_id
        }
        
        logger.info("Preparing API request",
                   message=message,
                   datetime=datetime_str,
                   cron_expression=cron_expression)
        
        try:
            # Отправка запроса к REST API
            response = await self.client.post(
                f"{self.rest_service_url}/api/cronjobs/",
                json=data
            )
            
            if response.status_code not in [200, 201]:
                logger.error("API request failed",
                           status_code=response.status_code,
                           response=response.text)
                raise ToolError(
                    message="Ошибка при создании напоминания",
                    error_code="API_ERROR",
                    details={
                        "status_code": response.status_code,
                        "response": response.text
                    }
                )
            
            job_data = response.json()
            logger.info("Reminder created successfully",
                       job_id=job_data["id"],
                       message=message)
            
            return f"Напоминание создано: {message} на {datetime_str}"
            
        except ToolError:
            raise
        except httpx.RequestError as e:
            logger.error("Request error",
                        error=str(e))
            raise ToolError(
                message="Ошибка при обращении к сервису напоминаний",
                error_code="SERVICE_ERROR",
                details={"error": str(e)}
            )
        except Exception as e:
            logger.error("Unknown error",
                        error=str(e),
                        exc_info=True)
            raise ToolError(
                message="Неизвестная ошибка при создании напоминания",
                error_code="UNKNOWN_ERROR",
                details={"error": str(e)}
            )
    
    def _datetime_to_cron(self, dt: datetime) -> str:
        """Преобразует datetime в CRON-выражение"""
        return f"{dt.minute} {dt.hour} {dt.day} {dt.month} *" 