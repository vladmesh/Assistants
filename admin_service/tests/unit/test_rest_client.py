from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from shared_models.api_schemas import TelegramUserRead

from rest_client import RestServiceClient

User = TelegramUserRead


@pytest.fixture
def mock_users():
    now = datetime.now(UTC).isoformat()
    return [
        {
            "id": 1,
            "telegram_id": 123456789,
            "username": "user1",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": 2,
            "telegram_id": 987654321,
            "username": "user2",
            "created_at": now,
            "updated_at": now,
        },
    ]


@pytest.fixture
def rest_client():
    """Create REST client with mocked request method."""
    with patch.object(RestServiceClient, "request", new_callable=AsyncMock) as mock:
        client = RestServiceClient(base_url="http://test-rest:8000")
        client._mock_request = mock
        yield client


@pytest.mark.asyncio
async def test_get_users_success(rest_client, mock_users):
    """Тест успешного получения списка пользователей."""
    rest_client._mock_request.return_value = mock_users

    users = await rest_client.get_users()

    assert len(users) == 2
    assert isinstance(users[0], User)
    assert users[0].id == 1
    assert users[0].telegram_id == 123456789
    assert users[0].username == "user1"
    assert users[1].id == 2
    assert users[1].telegram_id == 987654321
    assert users[1].username == "user2"

    rest_client._mock_request.assert_called_once_with("GET", "/api/users/")


@pytest.mark.asyncio
async def test_get_users_error(rest_client):
    """Тест обработки ошибки при получении списка пользователей."""
    rest_client._mock_request.side_effect = Exception("HTTP Error")

    with pytest.raises(Exception):
        await rest_client.get_users()

    rest_client._mock_request.assert_called_once_with("GET", "/api/users/")


@pytest.mark.asyncio
async def test_get_users_empty(rest_client):
    """Тест получения пустого списка пользователей."""
    rest_client._mock_request.return_value = []

    users = await rest_client.get_users()

    assert users == []
    rest_client._mock_request.assert_called_once_with("GET", "/api/users/")
