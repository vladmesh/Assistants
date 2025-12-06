from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest
from shared_models.api_schemas import AssistantRead, TelegramUserRead

from rest_client import RestServiceClient

# Use the correct names in tests
User = TelegramUserRead
Assistant = AssistantRead


class MockResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json_data = json_data

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "HTTP Error", request=MagicMock(), response=MagicMock()
            )


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
    return RestServiceClient(base_url="http://test-rest:8000")


@pytest.mark.asyncio
async def test_get_users_success(rest_client, mock_users):
    """Тест успешного получения списка пользователей."""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = MockResponse(200, mock_users)

        users = await rest_client.get_users()

        assert len(users) == 2
        assert isinstance(users[0], User)
        assert users[0].id == 1
        assert users[0].telegram_id == 123456789
        assert users[0].username == "user1"
        assert users[1].id == 2
        assert users[1].telegram_id == 987654321
        assert users[1].username == "user2"

        mock_get.assert_called_once_with("http://test-rest:8000/api/users/")


@pytest.mark.asyncio
async def test_get_users_error(rest_client):
    """Тест обработки ошибки при получении списка пользователей."""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = httpx.HTTPStatusError(
            "HTTP Error", request=MagicMock(), response=MagicMock()
        )

        with pytest.raises(httpx.HTTPStatusError):
            await rest_client.get_users()

        mock_get.assert_called_once_with("http://test-rest:8000/api/users/")


@pytest.mark.asyncio
async def test_close(rest_client):
    """Тест закрытия клиента."""
    with patch("httpx.AsyncClient.aclose") as mock_aclose:
        await rest_client.close()
        mock_aclose.assert_called_once()
