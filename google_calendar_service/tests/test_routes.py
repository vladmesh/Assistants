import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient
from src.main import app
from src.services.rest_service import RestService
from src.services.calendar import GoogleCalendarService

@pytest.mark.asyncio
async def test_get_auth_url():
    """Test getting auth URL for a user"""
    # Create mock for REST service
    mock_rest_service = AsyncMock(spec=RestService)
    mock_rest_service.get_user.return_value = {"id": 123, "name": "Test User"}
    mock_rest_service.get_calendar_token.return_value = None

    # Create mock for Calendar service
    mock_calendar_service = MagicMock(spec=GoogleCalendarService)
    mock_calendar_service.get_auth_url.return_value = "https://test.auth.url"

    # Store original services
    original_rest_service = app.state.rest_service
    original_calendar_service = app.state.calendar_service

    # Set up mocks
    app.state.rest_service = mock_rest_service
    app.state.calendar_service = mock_calendar_service

    try:
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/auth/url/123")
            
            # Verify response
            assert response.status_code == 200
            assert "auth_url" in response.json()
            assert response.json()["auth_url"] == "https://test.auth.url"
            
            # Verify service calls
            mock_rest_service.get_user.assert_called_once_with(123)
            mock_rest_service.get_calendar_token.assert_called_once_with("123")
            mock_calendar_service.get_auth_url.assert_called_once_with("123")
    finally:
        # Restore original services
        app.state.rest_service = original_rest_service
        app.state.calendar_service = original_calendar_service 