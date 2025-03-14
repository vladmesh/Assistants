from typing import Optional, Dict, Any, ClassVar
from datetime import datetime
from pydantic import BaseModel, Field
from tools.base import BaseTool
from config.settings import Settings
import httpx
import structlog

logger = structlog.get_logger()

class EventCreate(BaseModel):
    """Event creation model"""
    summary: str = Field(description="Event title")
    description: Optional[str] = Field(None, description="Event description")
    start: Dict[str, str] = Field(description="Event start time in format {'dateTime': '2023-12-08T12:00:00Z', 'timeZone': 'UTC'}")
    end: Dict[str, str] = Field(description="Event end time in format {'dateTime': '2023-12-08T12:30:00Z', 'timeZone': 'UTC'}")
    location: Optional[str] = Field(None, description="Event location")

class CalendarTool(BaseTool):
    """Tool for working with Google Calendar"""
    
    NAME: ClassVar[str] = "calendar"
    DESCRIPTION: ClassVar[str] = """Инструмент для работы с Google Calendar.
    
    Возможности:
    1. Получение списка событий
    2. Создание новых событий
    
    Параметры для создания события:
    - summary: Название события (обязательно)
    - description: Описание события (опционально)
    - start: Время начала события в формате {'dateTime': '2023-12-08T12:00:00Z', 'timeZone': 'UTC'} (обязательно)
    - end: Время окончания события в формате {'dateTime': '2023-12-08T12:30:00Z', 'timeZone': 'UTC'} (обязательно)
    - location: Место проведения события (опционально)
    """
    
    name: str = NAME
    description: str = DESCRIPTION
    base_url: str = "http://google_calendar_service:8000/api/v1"
    settings: Settings
    
    def __init__(self, settings: Settings, user_id: Optional[str] = None):
        super().__init__(
            name=self.NAME,
            description=self.DESCRIPTION,
            args_schema=EventCreate,
            settings=settings
        )
        self.user_id = user_id
    
    async def _arun(self, **kwargs) -> str:
        """Execute tool with arguments"""
        return await self._execute("create_event", **kwargs)
    
    async def _execute(
        self,
        action: str,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        start: Optional[Dict[str, str]] = None,
        end: Optional[Dict[str, str]] = None,
        location: Optional[str] = None
    ) -> str:
        """Execute calendar action"""
        try:
            if not self.user_id:
                raise ValueError("User ID is required")
            
            async with httpx.AsyncClient() as client:
                if action == "get_events":
                    # Get events
                    response = await client.get(
                        f"{self.base_url}/events/{self.user_id}",
                        params={
                            "time_min": time_min.isoformat() if time_min else None,
                            "time_max": time_max.isoformat() if time_max else None
                        }
                    )
                    
                    if response.status_code == 401:
                        # User not authorized, get auth URL
                        auth_response = await client.get(
                            f"{self.base_url}/auth/url/{self.user_id}"
                        )
                        auth_url = auth_response.json()["auth_url"]
                        return f"Для доступа к календарю необходимо авторизоваться. Перейдите по ссылке: {auth_url}"
                    
                    response.raise_for_status()
                    events = response.json()
                    
                    if not events:
                        return "У вас нет событий в указанный период"
                    
                    # Format events
                    result = "Ваши события:\n\n"
                    for event in events:
                        start = datetime.fromisoformat(event["start"]["dateTime"].replace("Z", "+00:00"))
                        end = datetime.fromisoformat(event["end"]["dateTime"].replace("Z", "+00:00"))
                        result += f"📅 {event['summary']}\n"
                        result += f"🕒 {start.strftime('%d.%m.%Y %H:%M')} - {end.strftime('%H:%M')}\n"
                        if event.get("location"):
                            result += f"📍 {event['location']}\n"
                        if event.get("description"):
                            result += f"📝 {event['description']}\n"
                        result += "\n"
                    
                    return result
                
                elif action == "create_event":
                    if not all([summary, start, end]):
                        raise ValueError("summary, start and end are required for creating an event")
                    
                    # Create event
                    event_data = {
                        "summary": summary,
                        "description": description,
                        "start": {
                            "dateTime": start["dateTime"].replace("+01:00", "Z"),
                            "timeZone": start["timeZone"]
                        },
                        "end": {
                            "dateTime": end["dateTime"].replace("+01:00", "Z"),
                            "timeZone": end["timeZone"]
                        },
                        "location": location
                    }
                    
                    # Remove None values and empty strings
                    event_data = {k: v for k, v in event_data.items() if v is not None and v != ""}
                    
                    response = await client.post(
                        f"{self.base_url}/events/{self.user_id}",
                        json=event_data
                    )
                    
                    if response.status_code == 401:
                        # User not authorized, get auth URL
                        auth_response = await client.get(
                            f"{self.base_url}/auth/url/{self.user_id}"
                        )
                        auth_url = auth_response.json()["auth_url"]
                        return f"Для создания события необходимо авторизоваться. Перейдите по ссылке: {auth_url}"
                    
                    response.raise_for_status()
                    created_event = response.json()
                    
                    return f"Событие '{created_event['summary']}' успешно создано!"
                
                else:
                    raise ValueError(f"Unknown action: {action}")
                    
        except httpx.HTTPError as e:
            logger.error("HTTP error", error=str(e), exc_info=True)
            raise
        except Exception as e:
            logger.error("Calendar tool error", error=str(e), exc_info=True)
            raise 