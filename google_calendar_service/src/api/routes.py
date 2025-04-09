from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from config.settings import Settings
from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from schemas.calendar import CreateEventRequest
from services.calendar import GoogleCalendarService
from services.redis_service import RedisService
from services.rest_service import RestService

from shared_models import TriggerType

logger = structlog.get_logger()
router = APIRouter()

# Create settings instance once
settings = Settings()


class EventBase(BaseModel):
    """Base model for event fields"""

    summary: str = Field(..., description="Event title")
    description: Optional[str] = Field(None, description="Event description")
    location: Optional[str] = Field(None, description="Event location")


class EventCreate(EventBase):
    """Model for event creation"""

    start: Dict[str, str] = Field(
        ..., description="Event start time with dateTime and timeZone"
    )
    end: Dict[str, str] = Field(
        ..., description="Event end time with dateTime and timeZone"
    )

    def to_google_format(self) -> Dict[str, Any]:
        """Convert event data to Google Calendar API format"""
        event = {"summary": self.summary, "start": self.start, "end": self.end}

        if self.description:
            event["description"] = self.description
        if self.location:
            event["location"] = self.location

        return event


class EventResponse(EventBase):
    """Model for event response"""

    id: str
    start: Dict[str, str]
    end: Dict[str, str]
    htmlLink: Optional[str] = None
    status: str


async def get_rest_service(request: Request) -> RestService:
    """Get REST service from app state"""
    return request.app.state.rest_service


async def get_calendar_service(request: Request) -> GoogleCalendarService:
    """Get Google Calendar service from app state"""
    return request.app.state.calendar_service


async def get_redis_service(request: Request) -> RedisService:
    """Get Redis service from app state"""
    return request.app.state.redis_service


@router.get("/auth/url/{user_id}")
async def get_auth_url(
    user_id: str,
    request: Request,
    rest_service: RestService = Depends(get_rest_service),
    calendar_service: GoogleCalendarService = Depends(get_calendar_service),
) -> Dict[str, str]:
    """Get Google OAuth URL for user authorization"""
    try:
        # Check if user exists
        user = await rest_service.get_user(int(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if user already has credentials
        # credentials = await rest_service.get_calendar_token(user_id)
        # if credentials:
        #     # Allow generating URL even if token exists (for re-authentication)
        #     # raise HTTPException(status_code=400, detail=\"User already authorized\")
        #     pass # Log maybe?
        #     logger.info(\"User already has credentials, but proceeding to generate auth URL for potential re-auth.\", user_id=user_id)

        # Get auth URL with state
        logger.info(f"Generating auth URL for user {user_id}")
        auth_url = calendar_service.get_auth_url(user_id)

        return {"auth_url": auth_url}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get auth URL", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/callback")
async def handle_callback(
    code: str,
    state: str,
    request: Request,
    rest_service: RestService = Depends(get_rest_service),
    calendar_service: GoogleCalendarService = Depends(get_calendar_service),
    redis_service: RedisService = Depends(get_redis_service),
) -> Response:
    """Handle OAuth callback"""
    try:
        # Parse user_id from state
        user_id = int(state)

        # Handle callback
        credentials = await calendar_service.handle_callback(code)

        # Save credentials to REST service
        success = await rest_service.update_calendar_token(
            user_id=user_id,
            access_token=credentials.token,
            refresh_token=credentials.refresh_token,
            token_expiry=credentials.expiry,
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to save credentials")

        # Send message to assistant
        await redis_service.send_to_assistant(
            user_id=user_id, trigger_type=TriggerType.GOOGLE_AUTH, payload={}
        )

        # Redirect to Telegram
        telegram_url = settings.TELEGRAM_DEEP_LINK_URL.format(
            TELEGRAM_BOT_USERNAME=settings.TELEGRAM_BOT_USERNAME
        )
        return Response(status_code=302, headers={"Location": telegram_url})

    except Exception as e:
        logger.error("Failed to handle callback", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/{user_id}")
async def get_events(
    user_id: str,
    time_min: Optional[datetime] = None,
    time_max: Optional[datetime] = None,
    rest_service: RestService = Depends(get_rest_service),
    calendar_service: GoogleCalendarService = Depends(get_calendar_service),
) -> List[Dict[str, Any]]:
    """Get user's calendar events"""
    try:
        # Get credentials from REST service
        credentials = await rest_service.get_calendar_token(int(user_id))
        if not credentials:
            raise HTTPException(status_code=401, detail="User not authorized")

        # Get events
        events = await calendar_service.get_events(credentials, time_min, time_max)

        return events

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error("Failed to get events", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/events/{user_id}", response_model=Dict[str, Any])
async def create_event(
    user_id: str,
    event: CreateEventRequest = Body(..., description="Event details"),
    rest_service: RestService = Depends(get_rest_service),
    calendar_service: GoogleCalendarService = Depends(get_calendar_service),
) -> Dict[str, Any]:
    """Create new calendar event using simplified data model"""
    try:
        # Get credentials from REST service
        credentials = await rest_service.get_calendar_token(int(user_id))
        if not credentials:
            raise HTTPException(status_code=401, detail="User not authorized")

        # Log event data
        logger.info("Received event data", user_id=user_id, event_data=event.dict())

        # Create event
        created_event = await calendar_service.create_event(credentials, event)

        logger.info(
            "Event created successfully",
            user_id=user_id,
            event_id=created_event.get("id"),
        )

        return created_event

    except ValueError as e:
        logger.error("Authorization error", error=str(e))
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error("Failed to create event", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
