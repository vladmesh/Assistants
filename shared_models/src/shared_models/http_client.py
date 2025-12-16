"""
Унифицированный HTTP-клиент для межсервисного взаимодействия.

Возможности:
- Retry с exponential backoff (tenacity)
- Circuit Breaker (pybreaker)
- Prometheus метрики
- Structured logging с correlation_id
- Настраиваемые таймауты
"""

import re
import time
from typing import Any, TypeVar

import httpx
from prometheus_client import Counter, Gauge, Histogram
from pybreaker import CircuitBreaker, CircuitBreakerError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from shared_models.logging import correlation_id_ctx, get_logger

logger = get_logger(__name__)

# === Prometheus Metrics ===

HTTP_REQUESTS_TOTAL = Counter(
    "http_client_requests_total",
    "Total HTTP requests made",
    ["service", "method", "endpoint", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "http_client_request_duration_seconds",
    "HTTP request duration in seconds",
    ["service", "method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

HTTP_RETRIES_TOTAL = Counter(
    "http_client_retries_total",
    "Total HTTP request retries",
    ["service", "method", "endpoint", "error_type"],
)

CIRCUIT_BREAKER_STATE = Gauge(
    "http_client_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half-open)",
    ["service", "target_service"],
)


# === Exceptions ===


class ServiceClientError(Exception):
    """Base exception for service client errors."""

    pass


class ServiceUnavailableError(ServiceClientError):
    """Target service is unavailable (circuit breaker open)."""

    pass


class ServiceTimeoutError(ServiceClientError):
    """Request timed out."""

    pass


class ServiceResponseError(ServiceClientError):
    """Service returned an error response."""

    def __init__(self, status_code: int, detail: str, response_body: str | None = None):
        self.status_code = status_code
        self.detail = detail
        self.response_body = response_body
        super().__init__(f"HTTP {status_code}: {detail}")


# === Configuration ===


class ClientConfig:
    """Configuration for BaseServiceClient."""

    def __init__(
        self,
        timeout: float = 30.0,
        connect_timeout: float = 5.0,
        max_retries: int = 3,
        retry_min_wait: float = 1.0,
        retry_max_wait: float = 10.0,
        circuit_breaker_fail_max: int = 5,
        circuit_breaker_reset_timeout: float = 30.0,
    ):
        self.timeout = timeout
        self.connect_timeout = connect_timeout
        self.max_retries = max_retries
        self.retry_min_wait = retry_min_wait
        self.retry_max_wait = retry_max_wait
        self.circuit_breaker_fail_max = circuit_breaker_fail_max
        self.circuit_breaker_reset_timeout = circuit_breaker_reset_timeout


DEFAULT_CONFIG = ClientConfig()


# === Base Client ===

T = TypeVar("T")


class BaseServiceClient:
    """
    Базовый HTTP-клиент для взаимодействия между сервисами.

    Использование:
        class MyRestClient(BaseServiceClient):
            def __init__(self):
                super().__init__(
                    base_url="http://rest_service:8000",
                    service_name="my_service",
                    target_service="rest_service",
                )

            async def get_user(self, user_id: int) -> dict:
                return await self.request("GET", f"/api/users/{user_id}")
    """

    def __init__(
        self,
        base_url: str,
        service_name: str,
        target_service: str,
        config: ClientConfig | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.service_name = service_name
        self.target_service = target_service
        self.config = config or DEFAULT_CONFIG

        # HTTP client
        self._client: httpx.AsyncClient | None = None

        # Circuit breaker per target service
        self._circuit_breaker = CircuitBreaker(
            fail_max=self.config.circuit_breaker_fail_max,
            reset_timeout=self.config.circuit_breaker_reset_timeout,
            name=f"{service_name}_to_{target_service}",
        )

        logger.info(
            "Service client initialized",
            service=service_name,
            target=target_service,
            base_url=base_url,
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy initialization of HTTP client."""
        if self._client is None or self._client.is_closed:
            timeout = httpx.Timeout(
                self.config.timeout,
                connect=self.config.connect_timeout,
            )
            self._client = httpx.AsyncClient(timeout=timeout)
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
            logger.info("Service client closed", service=self.service_name)

    async def __aenter__(self) -> "BaseServiceClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    def _update_circuit_breaker_metric(self) -> None:
        """Update Prometheus metric for circuit breaker state."""
        state_map = {"closed": 0, "open": 1, "half-open": 2}
        state = self._circuit_breaker.current_state
        CIRCUIT_BREAKER_STATE.labels(
            service=self.service_name,
            target_service=self.target_service,
        ).set(state_map.get(state, -1))

    def _get_retry_decorator(self, method: str, endpoint: str):
        """Create retry decorator with metrics."""

        def before_retry(retry_state):
            error = retry_state.outcome.exception()
            error_type = type(error).__name__
            HTTP_RETRIES_TOTAL.labels(
                service=self.service_name,
                method=method,
                endpoint=self._normalize_endpoint(endpoint),
                error_type=error_type,
            ).inc()
            logger.warning(
                "Retrying request",
                method=method,
                endpoint=endpoint,
                attempt=retry_state.attempt_number,
                error_type=error_type,
                error=str(error),
            )

        return retry(
            stop=stop_after_attempt(self.config.max_retries),
            wait=wait_exponential(
                multiplier=1,
                min=self.config.retry_min_wait,
                max=self.config.retry_max_wait,
            ),
            retry=retry_if_exception_type(
                (
                    httpx.TimeoutException,
                    httpx.ConnectError,
                    httpx.NetworkError,
                    httpx.HTTPStatusError,
                )
            ),
            before_sleep=before_retry,
            reraise=True,
        )

    async def request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any] | list[Any] | None:
        """
        Make an HTTP request with retry, circuit breaker, and metrics.

        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE)
            endpoint: API endpoint (e.g., "/api/users/1")
            **kwargs: Additional arguments for httpx (json, params, headers, etc.)

        Returns:
            Parsed JSON response or None for 204 No Content

        Raises:
            ServiceUnavailableError: Circuit breaker is open
            ServiceTimeoutError: Request timed out
            ServiceResponseError: Non-2xx response
        """
        full_url = f"{self.base_url}{endpoint}"
        correlation_id = correlation_id_ctx.get()

        # Add correlation_id header
        headers = kwargs.pop("headers", {})
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        kwargs["headers"] = headers

        # Check circuit breaker
        self._update_circuit_breaker_metric()
        if self._circuit_breaker.current_state == "open":
            logger.error(
                "Circuit breaker open, request blocked",
                method=method,
                endpoint=endpoint,
                target=self.target_service,
            )
            raise ServiceUnavailableError(
                f"Service {self.target_service} is unavailable (circuit breaker open)"
            )

        # Execute with retry
        start_time = time.perf_counter()
        status_code = "error"

        try:
            result = await self._execute_request(method, full_url, endpoint, **kwargs)
            status_code = "success"
            return result

        except httpx.TimeoutException as e:
            self._record_circuit_breaker_failure(e)
            raise ServiceTimeoutError(f"Request to {full_url} timed out") from e

        except httpx.HTTPStatusError as e:
            status_code = str(e.response.status_code)
            # Record failure for 5xx errors
            if e.response.status_code >= 500:
                self._record_circuit_breaker_failure(e)
            raise

        except ServiceResponseError as e:
            status_code = str(e.status_code)
            raise

        except Exception as e:
            self._record_circuit_breaker_failure(e)
            raise

        finally:
            duration = time.perf_counter() - start_time
            normalized_endpoint = self._normalize_endpoint(endpoint)

            HTTP_REQUESTS_TOTAL.labels(
                service=self.service_name,
                method=method,
                endpoint=normalized_endpoint,
                status=status_code,
            ).inc()

            HTTP_REQUEST_DURATION.labels(
                service=self.service_name,
                method=method,
                endpoint=normalized_endpoint,
            ).observe(duration)

            logger.debug(
                "HTTP request completed",
                method=method,
                endpoint=endpoint,
                status=status_code,
                duration_ms=round(duration * 1000),
                correlation_id=correlation_id,
            )

    def _record_circuit_breaker_failure(self, error: Exception) -> None:
        """Record failure in circuit breaker."""
        try:

            def raise_error():
                raise error

            self._circuit_breaker.call(raise_error)
        except (CircuitBreakerError, Exception):
            pass

    async def _execute_request(
        self,
        method: str,
        url: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any] | list[Any] | None:
        """Execute HTTP request with retry logic."""

        @self._get_retry_decorator(method, endpoint)
        async def _do_request():
            client = await self._get_client()
            response = await client.request(method, url, **kwargs)

            # Handle 5xx with retry
            if 500 <= response.status_code < 600:
                response.raise_for_status()

            # Handle 4xx without retry
            if response.status_code >= 400:
                error_detail = self._extract_error_detail(response)
                raise ServiceResponseError(
                    status_code=response.status_code,
                    detail=error_detail,
                    response_body=response.text,
                )

            # Handle 204 No Content
            if response.status_code == 204:
                return None

            # Handle empty response
            if not response.content:
                return None

            return response.json()

        return await _do_request()

    def _extract_error_detail(self, response: httpx.Response) -> str:
        """Extract error detail from response."""
        try:
            data = response.json()
            if isinstance(data, dict) and "detail" in data:
                return str(data["detail"])
        except Exception:
            pass
        return response.text[:500] if response.text else "Unknown error"

    @staticmethod
    def _normalize_endpoint(endpoint: str) -> str:
        """
        Normalize endpoint for metrics by replacing IDs with placeholders.
        /api/users/123 → /api/users/{id}
        /api/assistants/550e8400-e29b-41d4-a716-446655440000 → /api/assistants/{id}
        """
        # UUID pattern
        endpoint = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "{id}",
            endpoint,
            flags=re.IGNORECASE,
        )
        # Numeric ID pattern
        endpoint = re.sub(r"/\d+(?=/|$)", "/{id}", endpoint)
        return endpoint
