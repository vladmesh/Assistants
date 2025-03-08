from typing import Dict, Any, Optional, Type
from datetime import datetime
from langchain.tools import BaseTool
import httpx
from config.logger import get_logger
from utils.error_handler import ToolError
from pydantic import BaseModel, Field

logger = get_logger(__name__)

class ReminderSchema(BaseModel):
    """Schema for reminder creation."""
    message: str = Field(..., description="Текст напоминания")
    datetime: str = Field(..., description="Дата и время напоминания в формате ISO (YYYY-MM-DD HH:MM)")
    priority: str = Field(default="normal", description="Приоритет (normal, high, low)")

class ReminderTool(BaseTool):
    name: str = "reminder"
    description: str = """Инструмент для создания напоминаний.
    Используйте его, когда пользователь просит напомнить о чем-то в определенное время.
    
    Примеры использования:
    - "Напомни мне позвонить маме завтра в 15:00"
    - "Создай напоминание о встрече через 2 часа"
    - "Напомни мне о дедлайне через 3 дня в 18:00"
    
    Параметры:
    - message: Текст напоминания
    - datetime: Дата и время напоминания в формате ISO (YYYY-MM-DD HH:MM)
    - priority: Приоритет (normal, high, low)
    """
    rest_service_url: str = "http://rest_service:8000"
    client: Optional[httpx.AsyncClient] = None
    args_schema: Type[BaseModel] = ReminderSchema
    
    @property
    def openai_schema(self) -> Dict[str, Any]:
        """Возвращает схему инструмента в формате OpenAI"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": ReminderSchema.schema()
            }
        }
    
    def __init__(self, rest_service_url: str = "http://rest_service:8000"):
        super().__init__()
        self.rest_service_url = rest_service_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    def _run(self, message: str, datetime_str: str, priority: str = "normal") -> str:
        """Синхронный метод не используется"""
        raise NotImplementedError("Этот инструмент поддерживает только асинхронные вызовы")
    
    async def _arun(self, **kwargs) -> str:
        """Создает напоминание через REST API"""
        logger.info("Starting reminder creation",
                   kwargs=kwargs,
                   current_time=datetime.now().isoformat())
        
        # Валидация приоритета
        if kwargs.get("priority", "normal") not in ["normal", "high", "low"]:
            raise ToolError(
                message="Неверный приоритет",
                error_code="INVALID_PRIORITY",
                details={"priority": kwargs.get("priority"), "allowed_values": ["normal", "high", "low"]}
            )
        
        # Парсинг даты и времени
        try:
            logger.info("Parsing datetime",
                       datetime_str=kwargs["datetime"],
                       current_time=datetime.now().isoformat())
            
            reminder_datetime = datetime.fromisoformat(kwargs["datetime"])
            
            logger.info("Parsed datetime",
                       reminder_datetime=reminder_datetime.isoformat(),
                       current_time=datetime.now().isoformat(),
                       is_past=reminder_datetime < datetime.now())
            
            if reminder_datetime < datetime.now():
                raise ToolError(
                    message="Дата напоминания не может быть в прошлом",
                    error_code="INVALID_DATETIME",
                    details={"datetime": kwargs["datetime"]}
                )
        except ValueError as e:
            logger.error("Failed to parse datetime",
                        datetime_str=kwargs["datetime"],
                        error=str(e))
            raise ToolError(
                message="Неверный формат даты и времени",
                error_code="INVALID_DATETIME_FORMAT",
                details={"datetime": kwargs["datetime"], "error": str(e)}
            )
        
        # Создание CRON-выражения
        cron_expression = self._datetime_to_cron(reminder_datetime)
        
        # Получаем пользователя по telegram_id
        try:
            user_response = await self.client.get(
                f"{self.rest_service_url}/api/users/",
                params={"telegram_id": int(kwargs.get("user_id"))}
            )
            
            if user_response.status_code != 200:
                logger.error("Failed to get user",
                           status_code=user_response.status_code,
                           response=user_response.text)
                raise ToolError(
                    message="Пользователь не найден",
                    error_code="USER_NOT_FOUND",
                    details={"telegram_id": kwargs.get("user_id")}
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
            "name": kwargs["message"],
            "cron_expression": cron_expression,
            "priority": kwargs.get("priority", "normal"),
            "type": "notification",
            "user_id": user_id
        }
        
        logger.info("Preparing API request",
                   message=kwargs["message"],
                   datetime=kwargs["datetime"],
                   priority=kwargs.get("priority", "normal"),
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
                       message=kwargs["message"])
            
            return f"Напоминание создано: {kwargs['message']} на {kwargs['datetime']}"
            
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