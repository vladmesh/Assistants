"""Tests for BaseServiceClient."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from shared_models.http_client import (
    BaseServiceClient,
    ClientConfig,
    ServiceResponseError,
    ServiceTimeoutError,
    ServiceUnavailableError,
)


class MockServiceClient(BaseServiceClient):
    """Mock implementation of BaseServiceClient for testing."""

    def __init__(self, base_url: str = "http://test:8000", config: ClientConfig = None):
        super().__init__(
            base_url=base_url,
            service_name="test_service",
            target_service="target_service",
            config=config,
        )


@pytest.fixture
def client():
    return MockServiceClient()


@pytest.fixture
def client_fast_retry():
    """Client with fast retry for testing."""
    config = ClientConfig(
        max_retries=3,
        retry_min_wait=0.01,
        retry_max_wait=0.02,
    )
    return MockServiceClient(config=config)


def create_mock_response(
    status_code: int = 200, json_data: dict | list | None = None, text: str = ""
):
    """Create a mock httpx.Response."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.text = text
    response.content = json_data is not None or bool(text)
    response.json.return_value = json_data
    return response


class TestBaseServiceClient:
    """Tests for BaseServiceClient."""

    @pytest.mark.asyncio
    async def test_successful_get_request(self, client):
        """Test successful GET request."""
        expected = {"id": 1, "name": "test"}

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request.return_value = create_mock_response(200, expected)
            mock_get_client.return_value = mock_http_client

            result = await client.request("GET", "/api/test")

            assert result == expected
            mock_http_client.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_successful_post_request(self, client):
        """Test successful POST request."""
        expected = {"id": 1, "created": True}
        payload = {"name": "new item"}

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request.return_value = create_mock_response(201, expected)
            mock_get_client.return_value = mock_http_client

            result = await client.request("POST", "/api/test", json=payload)

            assert result == expected

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, client_fast_retry):
        """Test retry logic on timeout."""
        client = client_fast_retry

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            # First call times out, second succeeds
            mock_http_client.request.side_effect = [
                httpx.TimeoutException("timeout"),
                create_mock_response(200, {"success": True}),
            ]
            mock_get_client.return_value = mock_http_client

            result = await client.request("GET", "/api/test")

            assert result == {"success": True}
            assert mock_http_client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_connect_error(self, client_fast_retry):
        """Test retry logic on connection error."""
        client = client_fast_retry

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            # First two calls fail, third succeeds
            mock_http_client.request.side_effect = [
                httpx.ConnectError("connection refused"),
                httpx.ConnectError("connection refused"),
                create_mock_response(200, {"success": True}),
            ]
            mock_get_client.return_value = mock_http_client

            result = await client.request("GET", "/api/test")

            assert result == {"success": True}
            assert mock_http_client.request.call_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_4xx(self, client):
        """Test no retry on 4xx errors."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            response = create_mock_response(404, {"detail": "Not found"}, "Not found")
            mock_http_client.request.return_value = response
            mock_get_client.return_value = mock_http_client

            with pytest.raises(ServiceResponseError) as exc_info:
                await client.request("GET", "/api/test")

            assert exc_info.value.status_code == 404
            assert mock_http_client.request.call_count == 1  # No retry

    @pytest.mark.asyncio
    async def test_retry_on_5xx(self, client_fast_retry):
        """Test retry on 5xx errors."""
        client = client_fast_retry

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            error_response = create_mock_response(500, None, "Internal error")

            def raise_for_status():
                raise httpx.HTTPStatusError(
                    "500", request=MagicMock(), response=error_response
                )

            error_response.raise_for_status = raise_for_status
            mock_http_client.request.return_value = error_response
            mock_get_client.return_value = mock_http_client

            with pytest.raises(httpx.HTTPStatusError):
                await client.request("GET", "/api/test")

            # Should have retried max_retries times
            assert mock_http_client.request.call_count == 3

    @pytest.mark.asyncio
    async def test_204_returns_none(self, client):
        """Test 204 No Content returns None."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            response = create_mock_response(204)
            response.content = b""
            mock_http_client.request.return_value = response
            mock_get_client.return_value = mock_http_client

            result = await client.request("DELETE", "/api/test/1")

            assert result is None

    @pytest.mark.asyncio
    async def test_empty_response_returns_none(self, client):
        """Test empty response body returns None."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            response = create_mock_response(200)
            response.content = b""
            mock_http_client.request.return_value = response
            mock_get_client.return_value = mock_http_client

            result = await client.request("GET", "/api/test")

            assert result is None

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_when_open(self, client):
        """Test circuit breaker blocks requests when open."""
        # Mock the current_state property to return "open"
        with patch.object(
            type(client._circuit_breaker),
            "current_state",
            new_callable=lambda: property(lambda self: "open"),
        ):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await client.request("GET", "/api/test")

            assert "circuit breaker open" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_timeout_raises_service_timeout_error(self, client_fast_retry):
        """Test timeout exception is wrapped in ServiceTimeoutError."""
        client = client_fast_retry

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request.side_effect = httpx.TimeoutException("timeout")
            mock_get_client.return_value = mock_http_client

            with pytest.raises(ServiceTimeoutError) as exc_info:
                await client.request("GET", "/api/test")

            assert "timed out" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_correlation_id_header_added(self, client):
        """Test correlation_id is added to request headers."""
        from shared_models.logging import correlation_id_ctx

        correlation_id_ctx.set("test-correlation-123")

        try:
            with patch.object(client, "_get_client") as mock_get_client:
                mock_http_client = AsyncMock()
                mock_http_client.request.return_value = create_mock_response(
                    200, {"ok": True}
                )
                mock_get_client.return_value = mock_http_client

                await client.request("GET", "/api/test")

                call_args = mock_http_client.request.call_args
                headers = call_args.kwargs.get("headers", {})
                assert headers.get("X-Correlation-ID") == "test-correlation-123"
        finally:
            correlation_id_ctx.set(None)

    @pytest.mark.asyncio
    async def test_list_response(self, client):
        """Test handling of list JSON response."""
        expected = [{"id": 1}, {"id": 2}]

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request.return_value = create_mock_response(200, expected)
            mock_get_client.return_value = mock_http_client

            result = await client.request("GET", "/api/items")

            assert result == expected

    @pytest.mark.asyncio
    async def test_error_detail_extraction(self, client):
        """Test error detail is extracted from response."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            response = create_mock_response(
                400, {"detail": "Invalid input"}, '{"detail": "Invalid input"}'
            )
            mock_http_client.request.return_value = response
            mock_get_client.return_value = mock_http_client

            with pytest.raises(ServiceResponseError) as exc_info:
                await client.request("POST", "/api/test", json={})

            assert exc_info.value.detail == "Invalid input"
            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager properly closes client."""
        async with MockServiceClient() as client:
            with patch.object(client, "_get_client") as mock_get_client:
                mock_http_client = AsyncMock()
                mock_http_client.request.return_value = create_mock_response(
                    200, {"ok": True}
                )
                mock_get_client.return_value = mock_http_client

                result = await client.request("GET", "/api/test")
                assert result == {"ok": True}


class TestNormalizeEndpoint:
    """Tests for endpoint normalization."""

    def test_normalize_endpoint_uuid(self):
        """Test UUID normalization in endpoints."""
        endpoint = "/api/assistants/550e8400-e29b-41d4-a716-446655440000"
        normalized = BaseServiceClient._normalize_endpoint(endpoint)
        assert normalized == "/api/assistants/{id}"

    def test_normalize_endpoint_numeric(self):
        """Test numeric ID normalization in endpoints."""
        endpoint = "/api/users/123/messages/456"
        normalized = BaseServiceClient._normalize_endpoint(endpoint)
        assert normalized == "/api/users/{id}/messages/{id}"

    def test_normalize_endpoint_mixed(self):
        """Test mixed UUID and numeric IDs."""
        endpoint = "/api/users/42/assistants/550e8400-e29b-41d4-a716-446655440000/tools"
        normalized = BaseServiceClient._normalize_endpoint(endpoint)
        assert normalized == "/api/users/{id}/assistants/{id}/tools"

    def test_normalize_endpoint_no_ids(self):
        """Test endpoint without IDs stays unchanged."""
        endpoint = "/api/users"
        normalized = BaseServiceClient._normalize_endpoint(endpoint)
        assert normalized == "/api/users"

    def test_normalize_endpoint_trailing_id(self):
        """Test endpoint with trailing numeric ID."""
        endpoint = "/api/users/999"
        normalized = BaseServiceClient._normalize_endpoint(endpoint)
        assert normalized == "/api/users/{id}"


class TestClientConfig:
    """Tests for ClientConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ClientConfig()
        assert config.timeout == 30.0
        assert config.connect_timeout == 5.0
        assert config.max_retries == 3
        assert config.retry_min_wait == 1.0
        assert config.retry_max_wait == 10.0
        assert config.circuit_breaker_fail_max == 5
        assert config.circuit_breaker_reset_timeout == 30.0

    def test_custom_config(self):
        """Test custom configuration values."""
        config = ClientConfig(
            timeout=60.0,
            connect_timeout=10.0,
            max_retries=5,
            retry_min_wait=2.0,
            retry_max_wait=20.0,
            circuit_breaker_fail_max=10,
            circuit_breaker_reset_timeout=60.0,
        )
        assert config.timeout == 60.0
        assert config.connect_timeout == 10.0
        assert config.max_retries == 5
        assert config.retry_min_wait == 2.0
        assert config.retry_max_wait == 20.0
        assert config.circuit_breaker_fail_max == 10
        assert config.circuit_breaker_reset_timeout == 60.0


class TestClientInitialization:
    """Tests for client initialization."""

    def test_base_url_trailing_slash_removed(self):
        """Test trailing slash is removed from base_url."""
        client = MockServiceClient(base_url="http://test:8000/")
        assert client.base_url == "http://test:8000"

    def test_service_names_stored(self):
        """Test service names are stored correctly."""
        client = MockServiceClient()
        assert client.service_name == "test_service"
        assert client.target_service == "target_service"

    def test_default_config_used(self):
        """Test default config is used when not provided."""
        client = MockServiceClient()
        assert client.config.timeout == 30.0

    def test_custom_config_used(self):
        """Test custom config is used when provided."""
        config = ClientConfig(timeout=60.0)
        client = MockServiceClient(config=config)
        assert client.config.timeout == 60.0
