# telegram_bot_service/tests/unit/test_rest_client.py
"""Unit tests for REST client."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


@pytest.fixture
def mock_settings():
    """Mock settings for tests."""
    with patch("clients.rest.settings") as mock:
        mock.rest_service_url = "http://test-rest:8000"
        yield mock


@pytest.fixture
def rest_client(mock_settings):
    """Create RestClient instance with mocked settings."""
    from clients.rest import RestClient

    return RestClient()


class TestRestClientInit:
    """Tests for RestClient initialization."""

    def test_client_init(self, rest_client):
        """Test client initializes with correct base URL."""
        assert rest_client.base_url == "http://test-rest:8000"
        assert rest_client.api_prefix == "/api"
        assert rest_client.session is None


class TestRestClientContextManager:
    """Tests for RestClient context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_creates_session(self, rest_client):
        """Test that entering context creates aiohttp session."""
        async with rest_client:
            assert rest_client.session is not None
            assert not rest_client.session.closed

    @pytest.mark.asyncio
    async def test_context_manager_closes_session(self, rest_client):
        """Test that exiting context closes aiohttp session."""
        async with rest_client:
            session = rest_client.session
        assert session.closed


class TestRestClientMakeRequest:
    """Tests for _make_request method."""

    @pytest.mark.asyncio
    async def test_make_request_without_session_raises(self, rest_client):
        """Test that making request without session raises error."""
        from clients.rest import RestClientError

        with pytest.raises(RestClientError, match="Session is not initialized"):
            await rest_client._make_request("GET", "/test")

    @pytest.mark.asyncio
    async def test_make_request_returns_none_on_404(self, rest_client):
        """Test that 404 response returns None."""
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.request = MagicMock(return_value=mock_response)
        rest_client.session = mock_session

        result = await rest_client._make_request("GET", "/users/999")
        assert result is None

    @pytest.mark.asyncio
    async def test_make_request_returns_json_on_success(self, rest_client):
        """Test successful request returns JSON data."""
        expected_data = {"id": 1, "telegram_id": 12345}

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=expected_data)
        mock_response.raise_for_status = MagicMock()
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.request = MagicMock(return_value=mock_response)
        rest_client.session = mock_session

        result = await rest_client._make_request("GET", "/users/1")
        assert result == expected_data

    @pytest.mark.asyncio
    async def test_make_request_returns_empty_dict_on_204(self, rest_client):
        """Test that 204 response returns empty dict."""
        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.raise_for_status = MagicMock()
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.request = MagicMock(return_value=mock_response)
        rest_client.session = mock_session

        result = await rest_client._make_request("DELETE", "/users/1")
        assert result == {}


class TestRestClientParseResponse:
    """Tests for _parse_response method."""

    def test_parse_response_dict(self, rest_client):
        """Test parsing dict response into model."""
        from shared_models.api_schemas import TelegramUserRead

        data = {
            "id": 1,
            "telegram_id": 12345,
            "username": "test_user",
            "is_active": True,
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
        }

        result = rest_client._parse_response(
            data, TelegramUserRead, context={"test": True}
        )

        assert isinstance(result, TelegramUserRead)
        assert result.id == 1
        assert result.telegram_id == 12345

    def test_parse_response_list(self, rest_client):
        """Test parsing list response into list of models."""
        from shared_models.api_schemas import TelegramUserRead

        data = [
            {
                "id": 1,
                "telegram_id": 12345,
                "username": "user1",
                "is_active": True,
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-01T00:00:00",
            },
            {
                "id": 2,
                "telegram_id": 67890,
                "username": "user2",
                "is_active": True,
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-01T00:00:00",
            },
        ]

        result = rest_client._parse_response(
            data, TelegramUserRead, context={"test": True}
        )

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(u, TelegramUserRead) for u in result)

    def test_parse_response_invalid_data_raises(self, rest_client):
        """Test parsing invalid data raises RestClientError."""
        from shared_models.api_schemas import TelegramUserRead

        from clients.rest import RestClientError

        data = {"invalid": "data"}  # Missing required fields

        with pytest.raises(RestClientError, match="validation failed"):
            rest_client._parse_response(data, TelegramUserRead, context={"test": True})


class TestRestClientUserMethods:
    """Tests for user-related methods."""

    @pytest.mark.asyncio
    async def test_get_user_by_id_found(self, rest_client):
        """Test getting user by ID when found."""
        user_data = {
            "id": 1,
            "telegram_id": 12345,
            "username": "test_user",
            "is_active": True,
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
        }

        rest_client._make_request = AsyncMock(return_value=user_data)

        result = await rest_client.get_user_by_id(1)

        assert result is not None
        assert result.id == 1
        assert result.telegram_id == 12345
        rest_client._make_request.assert_called_once_with("GET", "/users/1")

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, rest_client):
        """Test getting user by ID when not found."""
        rest_client._make_request = AsyncMock(return_value=None)

        result = await rest_client.get_user_by_id(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_or_create_user_existing(self, rest_client):
        """Test get_or_create returns existing user."""
        user_data = {
            "id": 1,
            "telegram_id": 12345,
            "username": "test_user",
            "is_active": True,
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
        }

        rest_client._get_user = AsyncMock(return_value=MagicMock(**user_data))

        result = await rest_client.get_or_create_user(12345, "test_user")

        assert result.telegram_id == 12345
        rest_client._get_user.assert_called_once_with(12345)

    @pytest.mark.asyncio
    async def test_get_or_create_user_creates_new(self, rest_client):
        """Test get_or_create creates new user when not exists."""
        from shared_models.api_schemas import TelegramUserRead

        user_data = {
            "id": 1,
            "telegram_id": 12345,
            "username": "new_user",
            "is_active": True,
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
        }

        rest_client._get_user = AsyncMock(return_value=None)
        rest_client._create_user = AsyncMock(return_value=TelegramUserRead(**user_data))

        result = await rest_client.get_or_create_user(12345, "new_user")

        assert result.telegram_id == 12345
        rest_client._get_user.assert_called_once_with(12345)
        rest_client._create_user.assert_called_once_with(12345, "new_user")


class TestRestClientSecretaryMethods:
    """Tests for secretary-related methods."""

    @pytest.mark.asyncio
    async def test_list_secretaries(self, rest_client):
        """Test listing available secretaries."""
        secretary_id = uuid4()
        secretaries_data = [
            {
                "id": str(secretary_id),
                "name": "Test Secretary",
                "is_secretary": True,
                "model": "gpt-4",
                "assistant_type": "llm",
                "is_active": True,
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-01T00:00:00",
                "tools": [],
            }
        ]

        rest_client._make_request = AsyncMock(return_value=secretaries_data)

        result = await rest_client.list_secretaries()

        assert len(result) == 1
        assert result[0].name == "Test Secretary"
        rest_client._make_request.assert_called_once_with("GET", "/secretaries/")

    @pytest.mark.asyncio
    async def test_list_secretaries_empty(self, rest_client):
        """Test listing secretaries returns empty list on None."""
        rest_client._make_request = AsyncMock(return_value=None)

        result = await rest_client.list_secretaries()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_user_secretary(self, rest_client):
        """Test getting assigned secretary for user."""
        secretary_id = uuid4()
        secretary_data = {
            "id": str(secretary_id),
            "name": "My Secretary",
            "is_secretary": True,
            "model": "gpt-4",
            "assistant_type": "llm",
            "is_active": True,
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
            "tools": [],
        }

        rest_client._make_request = AsyncMock(return_value=secretary_data)

        result = await rest_client.get_user_secretary(1)

        assert result is not None
        assert result.name == "My Secretary"
        rest_client._make_request.assert_called_once_with("GET", "/users/1/secretary")

    @pytest.mark.asyncio
    async def test_get_user_secretary_not_assigned(self, rest_client):
        """Test getting secretary when none assigned."""
        rest_client._make_request = AsyncMock(return_value=None)

        result = await rest_client.get_user_secretary(1)

        assert result is None


class TestRestClientPing:
    """Tests for ping/health check method."""

    @pytest.mark.asyncio
    async def test_ping_success(self, rest_client):
        """Test successful ping."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "healthy"})
        mock_response.raise_for_status = MagicMock()
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        rest_client.session = mock_session

        result = await rest_client.ping()

        assert result is True

    @pytest.mark.asyncio
    async def test_ping_without_session(self, rest_client):
        """Test ping without session returns False."""
        # ping() catches the error internally and returns False
        result = await rest_client.ping()
        assert result is False

    @pytest.mark.asyncio
    async def test_ping_unhealthy_status(self, rest_client):
        """Test ping returns False for unhealthy status."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "unhealthy"})
        mock_response.raise_for_status = MagicMock()
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        rest_client.session = mock_session

        result = await rest_client.ping()

        assert result is False
