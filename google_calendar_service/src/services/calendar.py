from datetime import datetime, timedelta
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from shared_models.api_schemas import CalendarCredentialsRead

from config.logger import get_logger
from config.settings import Settings
from schemas.calendar import CreateEventRequest

logger = get_logger(__name__)


class GoogleCalendarService:
    """Service for working with Google Calendar API"""

    SCOPES = [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events",
    ]

    def __init__(self, settings: Settings):
        self.settings = settings

    def _make_flow(self) -> Flow:
        """Helper method to create a new Flow instance."""
        client_config = {
            "web": {
                "client_id": self.settings.GOOGLE_CLIENT_ID,
                "project_id": "smart-assistant",  # Or from settings if it varies
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": self.settings.GOOGLE_TOKEN_URI,
                "auth_provider_x509_cert_url": (
                    self.settings.GOOGLE_AUTH_PROVIDER_CERT_URL
                ),
                "client_secret": self.settings.GOOGLE_CLIENT_SECRET,
                "redirect_uris": [self.settings.GOOGLE_REDIRECT_URI],
            }
        }
        return Flow.from_client_config(
            client_config=client_config,
            scopes=self.SCOPES,
            redirect_uri=self.settings.GOOGLE_REDIRECT_URI,
        )

    def get_auth_url(self, state: str) -> str:
        """Get Google OAuth URL for user authorization"""
        flow = self._make_flow()
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state,
        )
        return auth_url

    async def handle_callback(self, code: str) -> Credentials:
        """Handle OAuth callback and return credentials"""
        try:
            flow = self._make_flow()
            # Exchange code for tokens
            flow.fetch_token(code=code)
            return flow.credentials
        except Exception as e:
            logger.error("Failed to handle callback", error=str(e))
            raise

    def _refresh_credentials_if_needed(self, credentials: Credentials) -> Credentials:
        """Refresh credentials if expired"""
        try:
            if credentials.expired:
                credentials.refresh(Request())
            return credentials
        except Exception as e:
            logger.error("Failed to refresh credentials", error=str(e))
            raise

    async def get_events(
        self,
        credentials_data: CalendarCredentialsRead,
        time_min: datetime | None = None,
        time_max: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Get user's calendar events"""
        try:
            # Create credentials object using attribute access
            credentials = Credentials(
                token=credentials_data.access_token,
                refresh_token=credentials_data.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.settings.GOOGLE_CLIENT_ID,
                client_secret=self.settings.GOOGLE_CLIENT_SECRET,
                scopes=self.SCOPES,
                expiry=credentials_data.token_expiry,
            )

            # Refresh if needed
            credentials = self._refresh_credentials_if_needed(credentials)

            service = build("calendar", "v3", credentials=credentials)

            # Set default time range if not provided
            if not time_min:
                time_min = datetime.utcnow()
            elif isinstance(time_min, str):
                time_min = datetime.fromisoformat(time_min)

            if not time_max:
                time_max = time_min + timedelta(days=7)
            elif isinstance(time_max, str):
                time_max = datetime.fromisoformat(time_max)

            # Ensure timezone info is present
            if time_min.tzinfo is None:
                time_min = time_min.replace(tzinfo=datetime.now().astimezone().tzinfo)
            if time_max.tzinfo is None:
                time_max = time_max.replace(tzinfo=datetime.now().astimezone().tzinfo)

            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min.isoformat(),  # RFC3339 with timezone
                    timeMax=time_max.isoformat(),  # RFC3339 with timezone
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            return events_result.get("items", [])

        except Exception as e:
            logger.error("Failed to get events", error=str(e))
            raise

    async def create_event(
        self, credentials_data: CalendarCredentialsRead, event_data: CreateEventRequest
    ) -> dict[str, Any]:
        """Create new calendar event using simplified data model"""
        try:
            # Create credentials object using attribute access
            credentials = Credentials(
                token=credentials_data.access_token,
                refresh_token=credentials_data.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.settings.GOOGLE_CLIENT_ID,
                client_secret=self.settings.GOOGLE_CLIENT_SECRET,
                scopes=self.SCOPES,
                expiry=credentials_data.token_expiry,
            )

            # Refresh if needed
            credentials = self._refresh_credentials_if_needed(credentials)

            service = build("calendar", "v3", credentials=credentials)

            # Log incoming event data
            logger.info("Creating event with data", event_data=event_data.dict())

            # Format event data according to Google Calendar API requirements
            formatted_event = {
                "summary": event_data.title,
                "start": {
                    "dateTime": event_data.start_time.date_time.isoformat(),
                    "timeZone": event_data.start_time.time_zone,
                },
                "end": {
                    "dateTime": event_data.end_time.date_time.isoformat(),
                    "timeZone": event_data.end_time.time_zone,
                },
            }

            # Add optional fields if present
            if event_data.description:
                formatted_event["description"] = event_data.description
            if event_data.location:
                formatted_event["location"] = event_data.location

            # Log formatted event data
            logger.info("Formatted event data", formatted_event=formatted_event)

            event = (
                service.events()
                .insert(calendarId="primary", body=formatted_event)
                .execute()
            )

            logger.info("Event created successfully", event_id=event.get("id"))
            return event

        except Exception as e:
            logger.error("Failed to create event", error=str(e))
            raise
