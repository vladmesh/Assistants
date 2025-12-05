import json
from datetime import datetime

import httpx
import structlog
from pydantic import BaseModel, Field

from tools.base import BaseTool

logger = structlog.get_logger()


class EventTime(BaseModel):
    """Model for event time with timezone"""

    date_time: str = Field(
        ...,
        description="Event time in ISO, e.g. YYYY-MM-DDTHH:MM:SS+HH:MM",
    )
    time_zone: str = Field(
        default="UTC", description="Timezone for the event (e.g., Europe/Moscow)"
    )


class CreateEventRequest(BaseModel):
    """Model for creating calendar event"""

    title: str = Field(..., description="Event title")
    start_time: EventTime = Field(..., description="Event start time")
    end_time: EventTime = Field(..., description="Event end time")
    description: str | None = Field(None, description="Event description")
    location: str | None = Field(None, description="Event location")


class ListEventsRequest(BaseModel):
    """Model for listing calendar events"""

    time_min: str | None = Field(
        None, description="Start time for event search in ISO format (optional)"
    )
    time_max: str | None = Field(
        None, description="End time for event search in ISO format (optional)"
    )


# --- Base Class for Calendar Tools ---
class BaseGoogleCalendarTool(BaseTool):
    """Base class for Google Calendar tools with common auth logic."""

    base_url: str = "http://google_calendar_service:8000"
    rest_url: str = "http://rest_service:8000/api"

    async def _check_auth(self, client: httpx.AsyncClient) -> str | None:
        """Check if user is authorized and return auth URL if not."""
        if not self.user_id:
            logger.warning("Cannot check auth without user_id")
            return "Error: User ID not available for authorization check."
        try:
            response = await client.get(
                f"{self.rest_url}/calendar/user/{self.user_id}/token", timeout=30.0
            )
            if response.status_code == 404 or (
                response.status_code == 200 and not response.json()
            ):
                # No token found, request auth URL
                auth_response = await client.get(
                    f"{self.base_url}/auth/url/{self.user_id}", timeout=30.0
                )
                auth_response.raise_for_status()
                auth_url = auth_response.json().get("auth_url")
                if auth_url:
                    logger.info(
                        "Authorization required, returning auth URL",
                        user_id=self.user_id,
                    )
                    return auth_url
                else:
                    logger.error("Auth URL not found in response", user_id=self.user_id)
                    return "Ошибка: Не удалось получить URL для авторизации Google."
            response.raise_for_status()  # Raise for other non-200 token check
            return None  # Token exists or other non-404 error handled below
        except httpx.HTTPStatusError as e:
            # Error during the token check itself (e.g., rest_service down)
            logger.error(
                "HTTP error checking authorization token",
                status_code=e.response.status_code,
                error=str(e),
                exc_info=True,
            )
            return (
                "Ошибка проверки токена авторизации "
                f"({e.response.status_code}): {e.response.text}"
            )
        except Exception as e:
            logger.error("Failed to check authorization", error=str(e), exc_info=True)
            return f"Ошибка проверки авторизации: {str(e)}"

    async def _handle_http_status_error(
        self,
        e: httpx.HTTPStatusError,
        client: httpx.AsyncClient,
        action: str = "выполнения операции",
    ) -> str:
        """Handles HTTPStatusError, checking for invalid_grant."""
        err_msg = f"Ошибка API календаря ({e.response.status_code}) при {action}"
        err_detail_text = e.response.text
        try:
            # Try to parse detail from JSON response
            err_detail = e.response.json().get("detail")
            if err_detail:
                err_detail_text = str(err_detail)
                err_msg += f": {err_detail_text}"
            else:
                err_msg += f": {err_detail_text}"
        except json.JSONDecodeError:
            err_msg += f": {err_detail_text}"

        logger.error(
            f"HTTP error during calendar {action}",
            error=err_msg,
            exc_info=True,
            status_code=e.response.status_code,
        )

        # Check for invalid_grant error specifically
        if e.response.status_code == 500 and "invalid_grant" in err_detail_text:
            logger.warning(
                "Invalid grant during calendar "
                f"{action}. Requesting re-authentication.",
                user_id=self.user_id,
            )
            # --- Directly request new auth URL instead of calling _check_auth ---
            auth_url = None
            try:
                logger.info(
                    "Requesting new auth URL for user "
                    f"{self.user_id} due to invalid_grant"
                )
                auth_response = await client.get(
                    f"{self.base_url}/auth/url/{self.user_id}", timeout=30.0
                )
                auth_response.raise_for_status()  # Raise for non-200 status
                auth_url = auth_response.json().get("auth_url")
                if not auth_url:
                    logger.error(
                        "Auth URL not found in response from calendar service",
                        user_id=self.user_id,
                        response_status=auth_response.status_code,
                    )
            except httpx.HTTPStatusError as auth_err:
                logger.error(
                    "HTTP error requesting new auth URL after invalid_grant",
                    user_id=self.user_id,
                    status_code=auth_err.response.status_code,
                    error=str(auth_err),
                    exc_info=True,
                )
            except Exception as auth_err:
                logger.error(
                    "Failed to request new auth URL after invalid_grant",
                    user_id=self.user_id,
                    error=str(auth_err),
                    exc_info=True,
                )
            # --- End of direct auth URL request ---

            if auth_url:  # Check if we successfully got the auth URL
                # Return the auth URL prompt
                return (
                    f"Для {action} необходимо повторно авторизоваться из-за "
                    f"недействительного токена. Перейдите по ссылке: {auth_url}"
                )
            else:
                # Fallback if getting auth URL failed
                logger.error(
                    "Failed to get re-authentication URL after invalid_grant",
                    user_id=self.user_id,
                )
                return (
                    f"Ошибка обновления токена Google при {action}. "
                    "Пожалуйста, попробуйте переподключить календарь или "
                    "обратитесь к администратору."
                )

        return err_msg  # Return original formatted error message if not invalid_grant


# --- Specific Calendar Tools ---
class CalendarCreateTool(BaseGoogleCalendarTool):
    """Tool for creating events in Google Calendar. Uses common base class."""

    args_schema: type[CreateEventRequest] = CreateEventRequest

    async def _execute(
        self,
        title: str,
        start_time: dict,
        end_time: dict,
        description: str | None = None,
        location: str | None = None,
    ) -> str:
        """Create new calendar event"""
        if not self.user_id:
            return "Ошибка: ID пользователя не найден."

        async with httpx.AsyncClient() as client:
            # Initial auth check
            auth_url = await self._check_auth(client)
            if auth_url is not None:
                if auth_url.startswith("Error:") or auth_url.startswith("Ошибка"):
                    return auth_url  # Return auth check error
                else:
                    # Return prompt to authorize
                    return (
                        "Для создания события необходимо авторизоваться. "
                        f"Перейдите по ссылке: {auth_url}"
                    )

            # Prepare event data (specific to create tool)
            # Ensure start_time and end_time are JSON-serializable dicts
            start_time_dict = (
                start_time.model_dump(mode="json")
                if hasattr(start_time, "model_dump")
                else start_time
            )
            end_time_dict = (
                end_time.model_dump(mode="json")
                if hasattr(end_time, "model_dump")
                else end_time
            )

            event_data = {
                "title": title,
                "start_time": start_time_dict,
                "end_time": end_time_dict,
            }
            if description:
                event_data["description"] = description
            if location:
                event_data["location"] = location

            try:
                # Make the API call (specific to create tool)
                response = await client.post(
                    f"{self.base_url}/events/{self.user_id}",
                    json=event_data,
                    timeout=30.0,
                )
                response.raise_for_status()
                created_event = response.json()
                return (
                    f"Событие '{created_event.get('summary', title)}' успешно создано!"
                )
            except httpx.HTTPStatusError as e:
                # Use the common handler from the base class
                return await self._handle_http_status_error(
                    e, client, action="создания события"
                )
            except httpx.RequestError as e:
                # Keep specific error message for network errors
                logger.error(
                    "Network error creating event", error=str(e), exc_info=True
                )
                return f"Сетевая ошибка при создании события: {str(e)}"
            except Exception as e:
                # Keep specific error message for other errors
                logger.error("Calendar create tool error", error=str(e), exc_info=True)
                return f"Непредвиденная ошибка при создании события: {str(e)}"


class CalendarListTool(BaseGoogleCalendarTool):
    """Tool for listing events from Google Calendar. Uses common base class."""

    args_schema: type[ListEventsRequest] = ListEventsRequest

    async def _execute(
        self, time_min: str | None = None, time_max: str | None = None
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
            # Initial auth check
            auth_url = await self._check_auth(client)
            if auth_url is not None:
                if auth_url.startswith("Error:") or auth_url.startswith("Ошибка"):
                    return auth_url  # Return auth check error
                else:
                    # Return prompt to authorize
                    logger.info("User needs authorization", user_id=self.user_id)
                    return (
                        "Для просмотра событий необходимо авторизоваться. "
                        f"Перейдите по ссылке: {auth_url}"
                    )

            # Prepare parameters (specific to list tool)
            params = {}
            if time_min:
                params["time_min"] = time_min
            if time_max:
                params["time_max"] = time_max

            try:
                # Make the API call (specific to list tool)
                response = await client.get(
                    f"{self.base_url}/events/{self.user_id}",
                    params=params,
                    timeout=30.0,
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

                # Format results (specific to list tool)
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

                    range_part = f" - {end_formatted}" if end_formatted else ""
                    result += f"- {summary} ({start_formatted}{range_part})\n"
                return result.strip()

            except httpx.HTTPStatusError as e:
                # Use the common handler from the base class
                return await self._handle_http_status_error(
                    e, client, action="получения событий"
                )
            except httpx.RequestError as e:
                # Keep specific error message for network errors
                logger.error(
                    "Network error listing events", error=str(e), exc_info=True
                )
                return f"Сетевая ошибка при получении событий: {str(e)}"
            except Exception as e:
                # Keep specific error message for other errors
                logger.error(
                    "Calendar list tool error",
                    error=str(e),
                    user_id=self.user_id,
                    exc_info=True,
                )
                return f"Непредвиденная ошибка при получении событий: {str(e)}"
