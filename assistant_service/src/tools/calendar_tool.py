from datetime import datetime
from typing import Optional, Type

import httpx
import structlog
from pydantic import BaseModel, Field
from tools.base import BaseTool

logger = structlog.get_logger()


class EventTime(BaseModel):
    """Model for event time with timezone"""

    date_time: str = Field(
        ...,
        description="Event date and time in ISO format (e.g., YYYY-MM-DDTHH:MM:SS+HH:MM)",
    )
    time_zone: str = Field(
        default="UTC", description="Timezone for the event (e.g., Europe/Moscow)"
    )


class CreateEventRequest(BaseModel):
    """Model for creating calendar event"""

    title: str = Field(..., description="Event title")
    start_time: EventTime = Field(..., description="Event start time")
    end_time: EventTime = Field(..., description="Event end time")
    description: Optional[str] = Field(None, description="Event description")
    location: Optional[str] = Field(None, description="Event location")


class ListEventsRequest(BaseModel):
    """Model for listing calendar events"""

    time_min: Optional[str] = Field(
        None, description="Start time for event search in ISO format (optional)"
    )
    time_max: Optional[str] = Field(
        None, description="End time for event search in ISO format (optional)"
    )


class CalendarCreateTool(BaseTool):
    """Tool for creating events in Google Calendar. Uses name/description from DB."""

    args_schema: Type[CreateEventRequest] = CreateEventRequest
    base_url: str = "http://google_calendar_service:8000"
    rest_url: str = "http://rest_service:8000/api"

    async def _check_auth(self, client: httpx.AsyncClient) -> Optional[str]:
        """Check if user is authorized and return auth URL if not."""
        if not self.user_id:
            logger.warning("Cannot check auth without user_id")
            return "Error: User ID not available for authorization check."
        try:
            response = await client.get(
                f"{self.rest_url}/calendar/user/{self.user_id}/token"
            )
            if response.status_code == 404 or (
                response.status_code == 200 and not response.json()
            ):
                auth_response = await client.get(
                    f"{self.base_url}/auth/url/{self.user_id}"
                )
                auth_response.raise_for_status()
                return auth_response.json()["auth_url"]
            response.raise_for_status()
            return None
        except Exception as e:
            logger.error("Failed to check authorization", error=str(e), exc_info=True)
            return f"Ошибка проверки авторизации: {str(e)}"

    async def _execute(
        self,
        title: str,
        start_time: dict,
        end_time: dict,
        description: Optional[str] = None,
        location: Optional[str] = None,
    ) -> str:
        """Create new calendar event"""
        if not self.user_id:
            return "Ошибка: ID пользователя не найден."

        async with httpx.AsyncClient() as client:
            auth_check_result = await self._check_auth(client)
            if auth_check_result is not None:
                if auth_check_result.startswith(
                    "Error:"
                ) or auth_check_result.startswith("Ошибка"):
                    return auth_check_result
                else:
                    return f"Для создания события необходимо авторизоваться. Перейдите по ссылке: {auth_check_result}"

            event_data = {
                "title": title,
                "start_time": start_time,
                "end_time": end_time,
            }
            if description:
                event_data["description"] = description
            if location:
                event_data["location"] = location

            logger.debug("Sending event data to calendar service", data=event_data)
            try:
                response = await client.post(
                    f"{self.base_url}/events/{self.user_id}", json=event_data
                )
                response.raise_for_status()
                created_event = response.json()
                return (
                    f"Событие '{created_event.get('summary', title)}' успешно создано!"
                )
            except httpx.HTTPStatusError as e:
                err_msg = f"Ошибка API календаря ({e.response.status_code})"
                try:
                    err_detail = e.response.json().get("detail")
                    err_msg += f": {err_detail}"
                except:
                    err_msg += f": {e.response.text}"
                logger.error("HTTP error creating event", error=err_msg, exc_info=True)
                return err_msg
            except httpx.RequestError as e:
                logger.error(
                    "Network error creating event", error=str(e), exc_info=True
                )
                return f"Сетевая ошибка при создании события: {str(e)}"
            except Exception as e:
                logger.error("Calendar create tool error", error=str(e), exc_info=True)
                return f"Непредвиденная ошибка при создании события: {str(e)}"


class CalendarListTool(BaseTool):
    """Tool for listing events from Google Calendar. Uses name/description from DB."""

    args_schema: Type[ListEventsRequest] = ListEventsRequest
    base_url: str = "http://google_calendar_service:8000"
    rest_url: str = "http://rest_service:8000/api"

    async def _check_auth(self, client: httpx.AsyncClient) -> Optional[str]:
        """Check if user is authorized and return auth URL if not."""
        if not self.user_id:
            logger.warning("Cannot check auth without user_id")
            return "Error: User ID not available for authorization check."
        try:
            response = await client.get(
                f"{self.rest_url}/calendar/user/{self.user_id}/token"
            )
            if response.status_code == 404 or (
                response.status_code == 200 and not response.json()
            ):
                auth_response = await client.get(
                    f"{self.base_url}/auth/url/{self.user_id}"
                )
                auth_response.raise_for_status()
                return auth_response.json()["auth_url"]
            response.raise_for_status()
            return None
        except Exception as e:
            logger.error("Failed to check authorization", error=str(e), exc_info=True)
            return f"Ошибка проверки авторизации: {str(e)}"

    async def _execute(
        self, time_min: Optional[str] = None, time_max: Optional[str] = None
    ) -> str:
        """Get calendar events"""
        if not self.user_id:
            return "Ошибка: ID пользователя не найден."

        logger.info(
            "Fetching calendar events",
            user_id=self.user_id,
            time_min=time_min,
            time_max=time_max,
        )
        async with httpx.AsyncClient() as client:
            auth_check_result = await self._check_auth(client)
            if auth_check_result is not None:
                if auth_check_result.startswith(
                    "Error:"
                ) or auth_check_result.startswith("Ошибка"):
                    return auth_check_result
                else:
                    logger.info("User needs authorization", user_id=self.user_id)
                    return f"Для просмотра событий необходимо авторизоваться. Перейдите по ссылке: {auth_check_result}"

            params = {}
            if time_min:
                params["time_min"] = time_min
            if time_max:
                params["time_max"] = time_max

            logger.debug(
                "Making request to calendar service",
                url=f"{self.base_url}/events/{self.user_id}",
                params=params,
            )
            try:
                response = await client.get(
                    f"{self.base_url}/events/{self.user_id}", params=params
                )
                response.raise_for_status()
                events = response.json()
                logger.info(
                    "Received calendar events",
                    user_id=self.user_id,
                    event_count=len(events),
                )

                if not events:
                    return "У вас нет событий в указанный период"

                result = "Ваши события:\n\n"
                for event in events:
                    summary = event.get("summary", "Без названия")
                    start_str = event.get("start", {}).get(
                        "dateTime", event.get("start", {}).get("date")
                    )
                    end_str = event.get("end", {}).get(
                        "dateTime", event.get("end", {}).get("date")
                    )
                    start_formatted = "Нет времени"
                    end_formatted = ""

                    if start_str:
                        try:
                            start_dt = datetime.fromisoformat(
                                start_str.replace("Z", "+00:00")
                            )
                            start_formatted = start_dt.strftime("%Y-%m-%d %H:%M")
                        except ValueError:
                            start_formatted = start_str

                    if end_str:
                        try:
                            end_dt = datetime.fromisoformat(
                                end_str.replace("Z", "+00:00")
                            )
                            if (
                                start_str
                                and start_dt.date() == end_dt.date()
                                and start_dt != end_dt
                            ):
                                end_formatted = end_dt.strftime("%H:%M")
                            elif start_str and start_dt.date() != end_dt.date():
                                end_formatted = end_dt.strftime("%Y-%m-%d %H:%M")
                            elif not start_str:
                                end_formatted = end_dt.strftime("%Y-%m-%d")
                        except ValueError:
                            if start_formatted != end_str:
                                end_formatted = end_str

                    result += f"- {summary} ({start_formatted}{f' - {end_formatted}' if end_formatted else ''})\n"
                return result.strip()

            except httpx.HTTPStatusError as e:
                err_msg = f"Ошибка API календаря ({e.response.status_code})"
                try:
                    err_detail = e.response.json().get("detail")
                    err_msg += f": {err_detail}"
                except:
                    err_msg += f": {e.response.text}"
                logger.error("HTTP error listing events", error=err_msg, exc_info=True)
                return err_msg
            except httpx.RequestError as e:
                logger.error(
                    "Network error listing events", error=str(e), exc_info=True
                )
                return f"Сетевая ошибка при получении событий: {str(e)}"
            except Exception as e:
                logger.error("Calendar list tool error", error=str(e), exc_info=True)
                return f"Непредвиденная ошибка при получении событий: {str(e)}"
