from typing import Optional, Dict
from datetime import datetime
import httpx
from log import logger

class CalendarTool:
    def __init__(self, base_url: str, user_id: str):
        self.base_url = base_url
        self.user_id = user_id

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
                        
                        # Create event in Google Calendar API format
                        event_data = {
                            "summary": summary,
                            "start": {
                                "dateTime": start["dateTime"],
                                "timeZone": start["timeZone"]
                            },
                            "end": {
                                "dateTime": end["dateTime"],
                                "timeZone": end["timeZone"]
                            }
                        }
                        
                        # Add optional fields if provided
                        if description:
                            event_data["description"] = description
                        if location:
                            event_data["location"] = location
                        
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