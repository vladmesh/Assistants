from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from src.config.settings import Settings
from src.config.logger import get_logger
from src.schemas.calendar import CreateEventRequest
import google_auth_oauthlib.flow

logger = get_logger(__name__)

class GoogleCalendarService:
    """Service for working with Google Calendar API"""
    
    SCOPES = [
        'https://www.googleapis.com/auth/calendar.readonly',
        'https://www.googleapis.com/auth/calendar.events'
    ]
    
    def __init__(self, settings: Settings):
        self.settings = settings
        
        # Create client configuration
        client_config = {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "project_id": "calendar-service",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uris": [settings.GOOGLE_REDIRECT_URI]
            }
        }
        
        # Create flow with redirect URI
        self._flow = Flow.from_client_config(
            client_config=client_config,
            scopes=self.SCOPES,
            redirect_uri=settings.GOOGLE_REDIRECT_URI
        )
    
    def get_auth_url(self, state: str) -> str:
        """Get Google OAuth URL for user authorization"""
        auth_url, _ = self._flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=state
        )
        
        return auth_url
    
    async def handle_callback(self, code: str) -> Credentials:
        """Handle OAuth callback and return credentials"""
        try:
            # Exchange code for tokens
            self._flow.fetch_token(code=code)
            return self._flow.credentials
            
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
    
    async def get_events(self, credentials_data: Dict[str, Any], 
                        time_min: Optional[datetime] = None,
                        time_max: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get user's calendar events"""
        try:
            # Create credentials object
            credentials = Credentials(
                token=credentials_data["access_token"],
                refresh_token=credentials_data["refresh_token"],
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.settings.GOOGLE_CLIENT_ID,
                client_secret=self.settings.GOOGLE_CLIENT_SECRET,
                scopes=self.SCOPES,
                expiry=datetime.fromisoformat(credentials_data["token_expiry"])
            )
            
            # Refresh if needed
            credentials = self._refresh_credentials_if_needed(credentials)
            
            service = build('calendar', 'v3', credentials=credentials)
            
            # Set default time range if not provided
            if not time_min:
                time_min = datetime.utcnow()
            if not time_max:
                time_max = time_min + timedelta(days=7)
            
            events_result = service.events().list(
                calendarId='primary',
                timeMin=time_min.isoformat() + 'Z',
                timeMax=time_max.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            return events_result.get('items', [])
            
        except Exception as e:
            logger.error("Failed to get events", error=str(e))
            raise
    
    async def create_event(self, credentials_data: Dict[str, Any], event_data: CreateEventRequest) -> Dict[str, Any]:
        """Create new calendar event using simplified data model"""
        try:
            # Create credentials object
            credentials = Credentials(
                token=credentials_data["access_token"],
                refresh_token=credentials_data["refresh_token"],
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.settings.GOOGLE_CLIENT_ID,
                client_secret=self.settings.GOOGLE_CLIENT_SECRET,
                scopes=self.SCOPES,
                expiry=datetime.fromisoformat(credentials_data["token_expiry"])
            )
            
            # Refresh if needed
            credentials = self._refresh_credentials_if_needed(credentials)
            
            service = build('calendar', 'v3', credentials=credentials)
            
            # Log incoming event data
            logger.info("Creating event with data", event_data=event_data.dict())
            
            # Format event data according to Google Calendar API requirements
            formatted_event = {
                "summary": event_data.title,
                "start": {
                    "dateTime": event_data.start_time.date_time.isoformat(),
                    "timeZone": event_data.start_time.time_zone
                },
                "end": {
                    "dateTime": event_data.end_time.date_time.isoformat(),
                    "timeZone": event_data.end_time.time_zone
                }
            }
            
            # Add optional fields if present
            if event_data.description:
                formatted_event["description"] = event_data.description
            if event_data.location:
                formatted_event["location"] = event_data.location
            
            # Log formatted event data
            logger.info("Formatted event data", formatted_event=formatted_event)
            
            event = service.events().insert(
                calendarId='primary',
                body=formatted_event
            ).execute()
            
            logger.info("Event created successfully", event_id=event.get("id"))
            return event
            
        except Exception as e:
            logger.error("Failed to create event", error=str(e))
            raise 