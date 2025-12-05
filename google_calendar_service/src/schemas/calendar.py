from datetime import datetime

from pydantic import BaseModel, Field


class EventTime(BaseModel):
    """Model for event time with timezone"""

    date_time: datetime = Field(..., description="Event date and time")
    time_zone: str = Field(default="UTC", description="Timezone for the event")


class CreateEventRequest(BaseModel):
    """Simplified model for creating calendar event"""

    title: str = Field(..., description="Event title")
    start_time: EventTime = Field(..., description="Event start time")
    end_time: EventTime = Field(..., description="Event end time")
    description: str | None = Field(None, description="Event description")
    location: str | None = Field(None, description="Event location")
