import pytest
from datetime import datetime, timedelta
from shared_models.calendar import (
    EventTime,
    EventBase,
    EventCreate,
    EventResponse,
    CreateEventRequest
)

def test_event_time():
    """Test EventTime model"""
    now = datetime.utcnow()
    event_time = EventTime(date_time=now, time_zone="UTC")
    
    assert event_time.date_time == now
    assert event_time.time_zone == "UTC"
    
    # Test default timezone
    event_time = EventTime(date_time=now)
    assert event_time.time_zone == "UTC"

def test_event_base():
    """Test EventBase model"""
    event = EventBase(
        summary="Test Event",
        description="Test Description",
        location="Test Location"
    )
    
    assert event.summary == "Test Event"
    assert event.description == "Test Description"
    assert event.location == "Test Location"
    
    # Test optional fields
    event = EventBase(summary="Test Event")
    assert event.description is None
    assert event.location is None

def test_event_create():
    """Test EventCreate model"""
    now = datetime.utcnow()
    event = EventCreate(
        summary="Test Event",
        description="Test Description",
        location="Test Location",
        start={"dateTime": now.isoformat(), "timeZone": "UTC"},
        end={"dateTime": (now + timedelta(hours=1)).isoformat(), "timeZone": "UTC"}
    )
    
    assert event.summary == "Test Event"
    assert event.description == "Test Description"
    assert event.location == "Test Location"
    assert "dateTime" in event.start
    assert "timeZone" in event.start
    assert "dateTime" in event.end
    assert "timeZone" in event.end
    
    # Test to_google_format
    google_format = event.to_google_format()
    assert google_format["summary"] == "Test Event"
    assert google_format["description"] == "Test Description"
    assert google_format["location"] == "Test Location"
    assert google_format["start"] == event.start
    assert google_format["end"] == event.end

def test_event_response():
    """Test EventResponse model"""
    now = datetime.utcnow()
    event = EventResponse(
        id="test_id",
        summary="Test Event",
        description="Test Description",
        location="Test Location",
        start={"dateTime": now.isoformat(), "timeZone": "UTC"},
        end={"dateTime": (now + timedelta(hours=1)).isoformat(), "timeZone": "UTC"},
        htmlLink="https://calendar.google.com/event",
        status="confirmed"
    )
    
    assert event.id == "test_id"
    assert event.summary == "Test Event"
    assert event.description == "Test Description"
    assert event.location == "Test Location"
    assert "dateTime" in event.start
    assert "timeZone" in event.start
    assert "dateTime" in event.end
    assert "timeZone" in event.end
    assert event.htmlLink == "https://calendar.google.com/event"
    assert event.status == "confirmed"

def test_create_event_request():
    """Test CreateEventRequest model"""
    now = datetime.utcnow()
    event = CreateEventRequest(
        title="Test Event",
        start_time=EventTime(date_time=now, time_zone="UTC"),
        end_time=EventTime(date_time=now + timedelta(hours=1), time_zone="UTC"),
        description="Test Description",
        location="Test Location"
    )
    
    assert event.title == "Test Event"
    assert event.start_time.date_time == now
    assert event.start_time.time_zone == "UTC"
    assert event.end_time.date_time == now + timedelta(hours=1)
    assert event.end_time.time_zone == "UTC"
    assert event.description == "Test Description"
    assert event.location == "Test Location"
    
    # Test optional fields
    event = CreateEventRequest(
        title="Test Event",
        start_time=EventTime(date_time=now),
        end_time=EventTime(date_time=now + timedelta(hours=1))
    )
    assert event.description is None
    assert event.location is None

def test_event_time_validation():
    """Test EventTime validation"""
    with pytest.raises(ValueError):
        EventTime(date_time="invalid_date")
    
    with pytest.raises(ValueError):
        EventTime(date_time=datetime.utcnow(), time_zone=123)  # timezone must be string

def test_event_base_validation():
    """Test EventBase validation"""
    with pytest.raises(ValueError):
        EventBase()  # summary is required
    
    with pytest.raises(ValueError):
        EventBase(summary=123)  # summary must be string

def test_event_create_validation():
    """Test EventCreate validation"""
    now = datetime.utcnow()
    with pytest.raises(ValueError):
        EventCreate(
            summary="Test Event",
            start={"invalid": "format"},
            end={"dateTime": now.isoformat(), "timeZone": "UTC"}
        )
    
    with pytest.raises(ValueError):
        EventCreate(
            summary="Test Event",
            start={"dateTime": now.isoformat(), "timeZone": "UTC"},
            end={"invalid": "format"}
        )

def test_create_event_request_validation():
    """Test CreateEventRequest validation"""
    with pytest.raises(ValueError):
        CreateEventRequest(
            title=123,  # title must be string
            start_time=EventTime(date_time=datetime.utcnow()),
            end_time=EventTime(date_time=datetime.utcnow() + timedelta(hours=1))
        ) 