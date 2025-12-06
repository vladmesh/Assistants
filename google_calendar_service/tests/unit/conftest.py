from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from main import app
from services.calendar import GoogleCalendarService
from services.redis_service import RedisService
from services.rest_service import RestService


@pytest.fixture
def mock_rest_service():
    """Create mock for REST service."""
    mock = AsyncMock(spec=RestService)
    mock.get_user.side_effect = lambda user_id: (
        {"id": 123, "name": "Test User"} if user_id == 123 else None
    )
    mock.get_calendar_token.return_value = None
    # Add mock for update_calendar_token used in callback route
    mock.update_calendar_token = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_calendar_service():
    """Create mock for Calendar service."""
    # Use AsyncMock instead of MagicMock
    mock = AsyncMock(spec=GoogleCalendarService)
    mock.get_auth_url.return_value = "https://test.auth.url"
    # Add mock for handle_callback used in callback route
    # Assuming handle_callback returns some credentials object or dict
    mock_creds = AsyncMock()
    mock_creds.token = "mock_access_token"
    mock_creds.refresh_token = "mock_refresh_token"
    mock_creds.expiry = datetime.now() + timedelta(hours=1)  # Example expiry
    mock.handle_callback = AsyncMock(return_value=mock_creds)
    return mock


@pytest.fixture
def mock_redis_service():
    """Create mock for Redis service."""
    mock = AsyncMock(spec=RedisService)
    mock.send_to_assistant = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_services(mock_rest_service, mock_calendar_service, mock_redis_service):
    """Setup and teardown mocked services."""
    # Store original services
    original_rest_service = getattr(app.state, "rest_service", None)
    original_calendar_service = getattr(app.state, "calendar_service", None)
    original_redis_service = getattr(app.state, "redis_service", None)

    # Set up mocks
    app.state.rest_service = mock_rest_service
    app.state.calendar_service = mock_calendar_service
    app.state.redis_service = mock_redis_service

    yield {
        "rest_service": mock_rest_service,
        "calendar_service": mock_calendar_service,
        "redis_service": mock_redis_service,
    }

    # Restore original services
    app.state.rest_service = original_rest_service
    app.state.calendar_service = original_calendar_service
    app.state.redis_service = original_redis_service
