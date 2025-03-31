from datetime import datetime
from typing import ClassVar, Optional

import httpx
import structlog
from config.settings import Settings
from pydantic import BaseModel, Field
from tools.base import BaseTool

logger = structlog.get_logger()


class EventTime(BaseModel):
    """Model for event time with timezone"""

    date_time: datetime = Field(..., description="Event date and time")
    time_zone: str = Field(default="UTC", description="Timezone for the event")


class CreateEventRequest(BaseModel):
    """Model for creating calendar event"""

    title: str = Field(..., description="Event title")
    start_time: EventTime = Field(..., description="Event start time")
    end_time: EventTime = Field(..., description="Event end time")
    description: Optional[str] = Field(None, description="Event description")
    location: Optional[str] = Field(None, description="Event location")


class ListEventsRequest(BaseModel):
    """Model for listing calendar events"""

    time_min: Optional[datetime] = Field(
        None, description="Start time for event search"
    )
    time_max: Optional[datetime] = Field(None, description="End time for event search")


class CalendarCreateTool(BaseTool):
    """Tool for creating events in Google Calendar"""

    NAME: ClassVar[str] = "calendar_create"
    DESCRIPTION: ClassVar[
        str
    ] = """Создает новое событие в Google Calendar.

    Параметры:
    - title: Название события (обязательно)
    - start_time: Время начала события с указанием таймзоны (обязательно)
    - end_time: Время окончания события с указанием таймзоны (обязательно)
    - description: Описание события (опционально)
    - location: Место проведения события (опционально)
    """

    name: str = NAME
    description: str = DESCRIPTION
    base_url: str = "http://google_calendar_service:8000"
    rest_url: str = "http://rest_service:8000/api"

    def __init__(self, settings: Settings, user_id: Optional[str] = None):
        super().__init__(
            name=self.NAME,
            description=self.DESCRIPTION,
            args_schema=CreateEventRequest,
            user_id=user_id,
        )

    async def _check_auth(self, client: httpx.AsyncClient) -> Optional[str]:
        """Check if user is authorized and return auth URL if not"""
        try:
            # Check token in REST service
            response = await client.get(
                f"{self.rest_url}/calendar/user/{self.user_id}/token"
            )
            if response.status_code == 404 or not response.json():
                # Get auth URL
                auth_response = await client.get(
                    f"{self.base_url}/auth/url/{self.user_id}"
                )
                return auth_response.json()["auth_url"]
            return None
        except Exception as e:
            logger.error("Failed to check authorization", error=str(e))
            raise

    async def _execute(
        self,
        title: str,
        start_time: EventTime,
        end_time: EventTime,
        description: Optional[str] = None,
        location: Optional[str] = None,
    ) -> str:
        """Create new calendar event"""
        try:
            if not self.user_id:
                raise ValueError("User ID is required")

            async with httpx.AsyncClient() as client:
                # Check authorization first
                auth_url = await self._check_auth(client)
                if auth_url:
                    return (
                        "Для создания события необходимо авторизоваться. Перейдите по"
                        f" ссылке: {auth_url}"
                    )

                event_data = {
                    "title": title,
                    "start_time": {
                        "date_time": start_time["date_time"],
                        "time_zone": start_time["time_zone"],
                    },
                    "end_time": {
                        "date_time": end_time["date_time"],
                        "time_zone": end_time["time_zone"],
                    },
                }

                if description:
                    event_data["description"] = description
                if location:
                    event_data["location"] = location

                response = await client.post(
                    f"{self.base_url}/events/{self.user_id}", json=event_data
                )

                response.raise_for_status()
                created_event = response.json()

                return f"Событие '{created_event['summary']}' успешно создано!"

        except httpx.HTTPError as e:
            logger.error("HTTP error", error=str(e), exc_info=True)
            raise
        except Exception as e:
            logger.error("Calendar create tool error", error=str(e), exc_info=True)
            raise


class CalendarListTool(BaseTool):
    """Tool for listing events from Google Calendar"""

    NAME: ClassVar[str] = "calendar_list"
    DESCRIPTION: ClassVar[
        str
    ] = """Получает список событий из Google Calendar.

    Параметры:
    - time_min: Начальное время для поиска событий (опционально)
    - time_max: Конечное время для поиска событий (опционально)

    Если время не указано, возвращает события на ближайшую неделю.
    """

    name: str = NAME
    description: str = DESCRIPTION
    base_url: str = "http://google_calendar_service:8000"
    rest_url: str = "http://rest_service:8000/api"

    def __init__(self, settings: Settings, user_id: Optional[str] = None):
        super().__init__(
            name=self.NAME,
            description=self.DESCRIPTION,
            args_schema=ListEventsRequest,
            user_id=user_id,
        )

    async def _check_auth(self, client: httpx.AsyncClient) -> Optional[str]:
        """Check if user is authorized and return auth URL if not"""
        try:
            # Check token in REST service
            response = await client.get(
                f"{self.rest_url}/calendar/user/{self.user_id}/token"
            )
            if response.status_code == 404 or not response.json():
                # Get auth URL
                auth_response = await client.get(
                    f"{self.base_url}/auth/url/{self.user_id}"
                )
                return auth_response.json()["auth_url"]
            return None
        except Exception as e:
            logger.error("Failed to check authorization", error=str(e))
            raise

    async def _execute(
        self, time_min: Optional[datetime] = None, time_max: Optional[datetime] = None
    ) -> str:
        """Get calendar events"""
        try:
            if not self.user_id:
                raise ValueError("User ID is required")

            logger.info(
                "Fetching calendar events",
                user_id=self.user_id,
                time_min=time_min,
                time_max=time_max,
            )

            async with httpx.AsyncClient() as client:
                # Check authorization first
                auth_url = await self._check_auth(client)
                if auth_url:
                    logger.info("User needs authorization", user_id=self.user_id)
                    return (
                        "Для просмотра событий необходимо авторизоваться. Перейдай"
                        f" ссылку пользователю: {auth_url}"
                    )

                params = {}
                if time_min:
                    if isinstance(time_min, str):
                        time_min = datetime.fromisoformat(
                            time_min.replace("Z", "+00:00")
                        )
                    params["time_min"] = time_min.isoformat()
                if time_max:
                    if isinstance(time_max, str):
                        time_max = datetime.fromisoformat(
                            time_max.replace("Z", "+00:00")
                        )
                    params["time_max"] = time_max.isoformat()

                logger.debug(
                    "Making request to calendar service",
                    url=f"{self.base_url}/events/{self.user_id}",
                    params=params,
                )

                response = await client.get(
                    f"{self.base_url}/events/{self.user_id}", params=params
                )

                response.raise_for_status()
                events = response.json()

                logger.info(
                    "Received calendar events",
                    user_id=self.user_id,
                    event_count=len(events),
                    calendar_events=events,
                )

                if not events:
                    return "У вас нет событий в указанный период"

                result = "Ваши события:\n\n"
                for event in events:
                    # Log raw event data for debugging
                    logger.debug("Processing calendar event", calendar_event=event)

                    # Handle both dateTime and date formats
                    start_data = event["start"]
                    end_data = event["end"]

                    logger.debug(
                        "Calendar event time data",
                        start_data=start_data,
                        end_data=end_data,
                    )

                    if "dateTime" in start_data:
                        # Event with specific time
                        start = datetime.fromisoformat(
                            start_data["dateTime"].replace("Z", "+00:00")
                        )
                        end = datetime.fromisoformat(
                            end_data["dateTime"].replace("Z", "+00:00")
                        )
                        time_str = (
                            f"{start.strftime('%d.%m.%Y %H:%M')} -"
                            f" {end.strftime('%H:%M')}"
                        )
                    else:
                        # All-day event
                        start = datetime.fromisoformat(start_data["date"])
                        time_str = f"{start.strftime('%d.%m.%Y')} (весь день)"

                    result += f"📅 {event['summary']}\n"
                    result += f"🕒 {time_str}\n"
                    if event.get("location"):
                        result += f"📍 {event['location']}\n"
                    if event.get("description"):
                        result += f"📝 {event['description']}\n"
                    result += "\n"

                logger.info(
                    "Successfully formatted calendar events",
                    user_id=self.user_id,
                    formatted_event_count=len(events),
                )
                return result

        except httpx.HTTPError as e:
            logger.error(
                "HTTP error while fetching calendar events",
                error=str(e),
                user_id=self.user_id,
                status_code=getattr(e.response, "status_code", None),
                response_text=getattr(e.response, "text", None),
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                "Calendar list tool error",
                error=str(e),
                user_id=self.user_id,
                exc_info=True,
            )
            raise
