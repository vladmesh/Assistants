import pytest
from datetime import datetime, timedelta
from shared_models.calendar import EventTime

@pytest.fixture
def sample_event_time():
    """Fixture for creating a sample EventTime"""
    return EventTime(
        date_time=datetime.utcnow(),
        time_zone="UTC"
    )

@pytest.fixture
def sample_event_times():
    """Fixture for creating sample start and end times"""
    now = datetime.utcnow()
    return {
        "start": EventTime(date_time=now, time_zone="UTC"),
        "end": EventTime(date_time=now + timedelta(hours=1), time_zone="UTC")
    } 