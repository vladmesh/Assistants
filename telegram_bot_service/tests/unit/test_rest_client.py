"""Unit tests for TelegramRestClient."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import pytest
from shared_models import ServiceClientError, ServiceResponseError


@pytest.fixture
def mock_settings():
    """Mock settings for tests."""
    with patch("clients.rest.settings") as mock:
        mock.rest_service_url = "http://test-rest:8000"
        yield mock


@pytest.fixture
def rest_client(mock_settings):
    """Create TelegramRestClient instance with mocked settings."""
    from clients.rest import TelegramRestClient

    return TelegramRestClient()


class TestTelegramRestClientInit:
    """Tests for TelegramRestClient initialization."""

    def test_client_init(self, rest_client):
        """Test client initializes with correct base URL."""
        assert rest_client.base_url == "http://test-rest:8000"
        assert rest_client.service_name == "telegram_bot_service"
        assert rest_client.target_service == "rest_service"


class TestTelegramRestClientContextManager:
    """Tests for TelegramRestClient context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_closes_client(self, rest_client):
        """Test that exiting context closes the client."""
        async with rest_client:
            pass
        # Client should be closed
        assert rest_client._client is None or rest_client._client.is_closed


class TestTelegramRestClientUserMethods:
    """Tests for user-related methods."""

    @pytest.mark.asyncio
    async def test_get_user_found(self, rest_client):
        """Test getting user when found."""
        user_data = {
            "id": 1,
            "telegram_id": 12345,
            "username": "test_user",
            "is_active": True,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        }

        rest_client.request = AsyncMock(return_value=user_data)

        result = await rest_client._get_user(12345)

        assert result is not None
        assert result.id == 1
        assert result.telegram_id == 12345
        rest_client.request.assert_called_once_with(
            "GET", "/api/users/by-telegram-id/", params={"telegram_id": 12345}
        )

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, rest_client):
        """Test getting user when not found (404)."""
        rest_client.request = AsyncMock(
            side_effect=ServiceResponseError(404, "Not found")
        )

        result = await rest_client._get_user(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_by_id_found(self, rest_client):
        """Test getting user by ID when found."""
        user_data = {
            "id": 1,
            "telegram_id": 12345,
            "username": "test_user",
            "is_active": True,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        }

        rest_client.request = AsyncMock(return_value=user_data)

        result = await rest_client.get_user_by_id(1)

        assert result is not None
        assert result.id == 1
        assert result.telegram_id == 12345
        rest_client.request.assert_called_once_with("GET", "/api/users/1")

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, rest_client):
        """Test getting user by ID when not found."""
        rest_client.request = AsyncMock(
            side_effect=ServiceResponseError(404, "Not found")
        )

        result = await rest_client.get_user_by_id(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_or_create_user_existing(self, rest_client):
        """Test get_or_create returns existing user."""
        from shared_models.api_schemas import TelegramUserRead

        user_data = {
            "id": 1,
            "telegram_id": 12345,
            "username": "test_user",
            "is_active": True,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        }

        rest_client._get_user = AsyncMock(return_value=TelegramUserRead(**user_data))

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
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        }

        rest_client._get_user = AsyncMock(return_value=None)
        rest_client._create_user = AsyncMock(return_value=TelegramUserRead(**user_data))

        result = await rest_client.get_or_create_user(12345, "new_user")

        assert result.telegram_id == 12345
        rest_client._get_user.assert_called_once_with(12345)
        rest_client._create_user.assert_called_once_with(12345, "new_user")


class TestTelegramRestClientSecretaryMethods:
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
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z",
                "tools": [],
            }
        ]

        rest_client.request = AsyncMock(return_value=secretaries_data)

        result = await rest_client.list_secretaries()

        assert len(result) == 1
        assert result[0].name == "Test Secretary"
        rest_client.request.assert_called_once_with("GET", "/api/secretaries/")

    @pytest.mark.asyncio
    async def test_list_secretaries_empty(self, rest_client):
        """Test listing secretaries returns empty list on None."""
        rest_client.request = AsyncMock(return_value=None)

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
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
            "tools": [],
        }

        rest_client.request = AsyncMock(return_value=secretary_data)

        result = await rest_client.get_user_secretary(1)

        assert result is not None
        assert result.name == "My Secretary"
        rest_client.request.assert_called_once_with("GET", "/api/users/1/secretary")

    @pytest.mark.asyncio
    async def test_get_user_secretary_not_assigned(self, rest_client):
        """Test getting secretary when none assigned."""
        rest_client.request = AsyncMock(
            side_effect=ServiceResponseError(404, "Not found")
        )

        result = await rest_client.get_user_secretary(1)

        assert result is None


class TestTelegramRestClientPing:
    """Tests for ping/health check method."""

    @pytest.mark.asyncio
    async def test_ping_success(self, rest_client):
        """Test successful ping."""
        rest_client.request = AsyncMock(return_value={"status": "healthy"})

        result = await rest_client.ping()

        assert result is True
        rest_client.request.assert_called_once_with("GET", "/health")

    @pytest.mark.asyncio
    async def test_ping_unhealthy_status(self, rest_client):
        """Test ping returns False for unhealthy status."""
        rest_client.request = AsyncMock(return_value={"status": "unhealthy"})

        result = await rest_client.ping()

        assert result is False

    @pytest.mark.asyncio
    async def test_ping_failure(self, rest_client):
        """Test ping returns False on error."""
        rest_client.request = AsyncMock(side_effect=Exception("Connection error"))

        result = await rest_client.ping()

        assert result is False


class TestTelegramRestClientRetryAndCircuitBreaker:
    """Tests for retry logic and circuit breaker (inherited from BaseServiceClient)."""

    @pytest.mark.asyncio
    async def test_timeout_raises_service_timeout_error(self, rest_client):
        """Test that timeout raises ServiceTimeoutError."""
        from shared_models import ServiceTimeoutError

        rest_client._execute_request = AsyncMock(
            side_effect=httpx.TimeoutException("timeout")
        )

        with pytest.raises(ServiceTimeoutError):
            await rest_client.request("GET", "/api/users/1")

    @pytest.mark.asyncio
    async def test_no_retry_on_4xx(self, rest_client):
        """Test no retry on 4xx errors."""
        rest_client._execute_request = AsyncMock(
            side_effect=ServiceResponseError(400, "Bad request")
        )

        with pytest.raises(ServiceResponseError) as exc_info:
            await rest_client.request("GET", "/api/test")

        assert exc_info.value.status_code == 400


class TestTelegramRestClientParseResponse:
    """Tests for _parse_response method."""

    def test_parse_response_dict(self, rest_client):
        """Test parsing dict response into model."""
        from shared_models.api_schemas import TelegramUserRead

        data = {
            "id": 1,
            "telegram_id": 12345,
            "username": "test_user",
            "is_active": True,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
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
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z",
            },
            {
                "id": 2,
                "telegram_id": 67890,
                "username": "user2",
                "is_active": True,
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z",
            },
        ]

        result = rest_client._parse_response(
            data, TelegramUserRead, context={"test": True}
        )

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(u, TelegramUserRead) for u in result)

    def test_parse_response_invalid_data_raises(self, rest_client):
        """Test parsing invalid data raises ServiceClientError."""
        from shared_models.api_schemas import TelegramUserRead

        data = {"invalid": "data"}  # Missing required fields

        with pytest.raises(ServiceClientError, match="validation failed"):
            rest_client._parse_response(data, TelegramUserRead, context={"test": True})
