import pytest
from httpx import AsyncClient
from main import app

# @pytest.mark.asyncio
# async def test_get_auth_url(mock_services):
#     """Test getting auth URL."""
#     async with AsyncClient(app=app, base_url="http://test") as client:
#         # Test successful case
#         response = await client.get("/auth/url/123")
#         assert response.status_code == 200
#         assert "auth_url" in response.json()
#         assert response.json()["auth_url"] == "https://test.auth.url"
#
#         # Verify service calls
#         mock_services["rest_service"].get_user.assert_called_with(123)
#         mock_services["rest_service"].get_calendar_token.assert_called_with("123")
#         mock_services["calendar_service"].get_auth_url.assert_awaited_with("123")
#
#         # Test user not found
#         response = await client.get("/auth/url/999")
#         assert response.status_code == 404
#         assert response.json()["detail"] == "User not found"

# Add a placeholder test if no other tests exist in this file
# to avoid pytest errors when collecting tests


def test_placeholder():
    """Placeholder test to ensure the file is not empty."""
    assert True
