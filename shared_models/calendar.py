from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class EventTime(BaseModel):
    """Model for event time with timezone"""
    date_time: datetime = Field(..., description="Event date and time")
    time_zone: str = Field(default="UTC", description="Timezone for the event")

class EventBase(BaseModel):
    """Base model for event fields"""
    summary: str = Field(..., description="Event title")
    description: Optional[str] = Field(None, description="Event description")
    location: Optional[str] = Field(None, description="Event location")

class EventCreate(EventBase):
    """Model for event creation"""
    start: Dict[str, str] = Field(..., description="Event start time with dateTime and timeZone")
    end: Dict[str, str] = Field(..., description="Event end time with dateTime and timeZone")

    def to_google_format(self) -> Dict[str, Any]:
        """Convert event data to Google Calendar API format"""
        event = {
            "summary": self.summary,
            "start": self.start,
            "end": self.end
        }
        
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

    class Config:
        from_attributes = True

class CreateEventRequest(BaseModel):
    """Simplified model for creating calendar event"""
    title: str = Field(..., description="Event title")
    start_time: EventTime = Field(..., description="Event start time")
    end_time: EventTime = Field(..., description="Event end time")
    description: Optional[str] = Field(None, description="Event description")
    location: Optional[str] = Field(None, description="Event location") 