import pytest
from unittest.mock import AsyncMock, MagicMock
from src.services.rest_service import RestService
from src.services.calendar import GoogleCalendarService
from src.main import app

@pytest.fixture
def mock_rest_service():
    """Create mock for REST service."""
    mock = AsyncMock(spec=RestService)
    mock.get_user.side_effect = lambda user_id: (
        {"id": 123, "name": "Test User"} if user_id == 123 else None
    )
    mock.get_calendar_token.return_value = None
    return mock

@pytest.fixture
def mock_calendar_service():
    """Create mock for Calendar service."""
    mock = MagicMock(spec=GoogleCalendarService)
    mock.get_auth_url.return_value = "https://test.auth.url"
    return mock

@pytest.fixture
def mock_services(mock_rest_service, mock_calendar_service):
    """Setup and teardown mocked services."""
    # Store original services
    original_rest_service = app.state.rest_service
    original_calendar_service = app.state.calendar_service

    # Set up mocks
    app.state.rest_service = mock_rest_service
    app.state.calendar_service = mock_calendar_service

    yield {
        "rest_service": mock_rest_service,
        "calendar_service": mock_calendar_service
    }

    # Restore original services
    app.state.rest_service = original_rest_service
    app.state.calendar_service = original_calendar_service 