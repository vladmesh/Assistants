# План рефакторинга межсервисной коммуникации

> **Цель:** Унифицировать HTTP-клиенты между сервисами, вынести подходящие операции в Redis, добавить мониторинг всех межсервисных вызовов.

## Оглавление
1. [Текущее состояние](#1-текущее-состояние)
2. [Целевая архитектура](#2-целевая-архитектура)
3. [Фаза 1: Базовый HTTP-клиент в shared_models](#фаза-1-базовый-http-клиент-в-shared_models)
4. [Фаза 2: Миграция сервисов на единый клиент](#фаза-2-миграция-сервисов-на-единый-клиент)
5. [Фаза 3: Вынос операций в Redis](#фаза-3-вынос-операций-в-redis)
6. [Фаза 4: Мониторинг и дашборды](#фаза-4-мониторинг-и-дашборды)
7. [Фаза 5: Тестирование](#фаза-5-тестирование)
8. [Риски и митигация](#риски-и-митигация)
9. [Чеклист готовности](#чеклист-готовности)

---

## 1. Текущее состояние

### 1.1 HTTP-клиенты по сервисам

| Сервис | Файл | Библиотека | Async | Retry | Timeout | Circuit Breaker |
|--------|------|------------|-------|-------|---------|-----------------|
| `assistant_service` | `services/rest_service.py` | `httpx` | Да | 3x exponential (tenacity) | 60s + 5s connect | Нет |
| `cron_service` | `rest_client.py` | `requests` | **Нет** | **Нет** | 10-30s | Нет |
| `admin_service` | `rest_client.py` | `httpx` | Да | **Нет** | Default | Нет |
| `rag_service` | `services/memory_service.py` | `httpx` | Да | **Нет** | 30s | Нет |
| `google_calendar_service` | `services/rest_service.py` | `httpx` | Да | **Нет** | Default | Нет |
| `telegram_bot_service` | inline in handlers | `httpx` | Да | **Нет** | Default | Нет |

**Проблемы:**
- ~1200 строк дублированного кода
- `cron_service` синхронный — блокирует event loop APScheduler
- Отсутствие retry в 5 из 6 сервисов → потеря данных при временных сбоях
- Разные форматы ошибок и логирования
- Нет метрик HTTP вызовов

### 1.2 Текущее использование Redis

```
┌─────────────────────────────────────────────────────────────────┐
│                    Redis Streams (уже есть)                      │
├─────────────────────────────────────────────────────────────────┤
│  queue:to_secretary    │ telegram → assistant (messages)        │
│  queue:to_telegram     │ assistant → telegram (responses)       │
│  queue:to_secretary    │ cron → assistant (triggers)            │
└─────────────────────────────────────────────────────────────────┘
```

**Не используется Redis для:**
- Кэширование конфигураций (assistants, tools, settings)
- Pub/Sub для инвалидации кэша
- Broadcast событий (user updated, assistant updated)

---

## 2. Целевая архитектура

### 2.1 Коммуникационная модель

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Целевая архитектура                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐              │
│  │  Telegram    │      │  Assistant   │      │    Cron      │              │
│  │    Bot       │      │   Service    │      │   Service    │              │
│  └──────┬───────┘      └──────┬───────┘      └──────┬───────┘              │
│         │                     │                     │                       │
│         │    BaseServiceClient (shared_models)      │                       │
│         │    ├── Retry (3x exponential)             │                       │
│         │    ├── Circuit Breaker                    │                       │
│         │    ├── Metrics (prometheus)               │                       │
│         │    └── Structured logging                 │                       │
│         │                     │                     │                       │
│         ▼                     ▼                     ▼                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         REST Service                                 │   │
│  │                    (CRUD, бизнес-логика)                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Redis                                        │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │   │
│  │  │   Streams   │  │    Cache    │  │   Pub/Sub   │                  │   │
│  │  │  (messages) │  │  (config)   │  │ (invalidate)│                  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Prometheus                                    │   │
│  │  http_requests_total, http_request_duration_seconds,                │   │
│  │  circuit_breaker_state, redis_operations_total                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Разделение ответственности

| Механизм | Используется для |
|----------|------------------|
| **REST (sync)** | CRUD операции, запросы с немедленным ответом, админка |
| **Redis Streams** | Асинхронные сообщения, триггеры, events без ожидания ответа |
| **Redis Cache** | Конфигурации (assistants, tools, settings), часто читаемые данные |
| **Redis Pub/Sub** | Инвалидация кэша при изменениях |

---

## Фаза 1: Базовый HTTP-клиент в shared_models

**Срок:** 4-6 часов  
**Приоритет:** Высокий

### 1.1 Создание BaseServiceClient

**Файл:** `shared_models/src/shared_models/http_client.py`

```python
"""
Унифицированный HTTP-клиент для межсервисного взаимодействия.

Возможности:
- Retry с exponential backoff (tenacity)
- Circuit Breaker (pybreaker)
- Prometheus метрики
- Structured logging с correlation_id
- Настраиваемые таймауты
"""

import time
from typing import Any, TypeVar
from contextlib import asynccontextmanager

import httpx
import structlog
from prometheus_client import Counter, Histogram, Gauge
from pybreaker import CircuitBreaker, CircuitBreakerError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
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
                endpoint=endpoint,
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
            retry=retry_if_exception_type((
                httpx.TimeoutException,
                httpx.ConnectError,
                httpx.NetworkError,
            )),
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
            result = await self._execute_request(method, full_url, **kwargs)
            status_code = "success"
            return result
        
        except httpx.TimeoutException as e:
            self._circuit_breaker.call(lambda: (_ for _ in ()).throw(e))
            raise ServiceTimeoutError(f"Request to {full_url} timed out") from e
        
        except httpx.HTTPStatusError as e:
            status_code = str(e.response.status_code)
            # Record failure for 5xx errors
            if e.response.status_code >= 500:
                try:
                    self._circuit_breaker.call(lambda: (_ for _ in ()).throw(e))
                except CircuitBreakerError:
                    pass
            raise
        
        except Exception as e:
            try:
                self._circuit_breaker.call(lambda: (_ for _ in ()).throw(e))
            except CircuitBreakerError:
                pass
            raise
        
        finally:
            duration = time.perf_counter() - start_time
            # Normalize endpoint for metrics (remove IDs)
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
    
    async def _execute_request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> dict[str, Any] | list[Any] | None:
        """Execute HTTP request with retry logic."""
        
        @self._get_retry_decorator(method, url)
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
        import re
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
```

### 1.2 Добавление зависимостей

**Файл:** `shared_models/pyproject.toml`

```toml
[tool.poetry.dependencies]
# ... existing ...
httpx = "^0.27.0"
tenacity = "^8.2.3"
pybreaker = "^1.2.0"
prometheus-client = "^0.19.0"
```

### 1.3 Экспорт из shared_models

**Файл:** `shared_models/src/shared_models/__init__.py`

```python
# ... existing exports ...
from shared_models.http_client import (
    BaseServiceClient,
    ClientConfig,
    ServiceClientError,
    ServiceUnavailableError,
    ServiceTimeoutError,
    ServiceResponseError,
)
```

### 1.4 Unit-тесты для BaseServiceClient

**Файл:** `shared_models/tests/unit/test_http_client.py`

```python
"""Tests for BaseServiceClient."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from shared_models.http_client import (
    BaseServiceClient,
    ClientConfig,
    ServiceResponseError,
    ServiceTimeoutError,
    ServiceUnavailableError,
)


class TestClient(BaseServiceClient):
    """Test implementation of BaseServiceClient."""
    
    def __init__(self, base_url: str = "http://test:8000"):
        super().__init__(
            base_url=base_url,
            service_name="test_service",
            target_service="target_service",
        )


@pytest.fixture
def client():
    return TestClient()


@pytest.fixture
def mock_response():
    """Create a mock httpx.Response."""
    def _create(status_code: int = 200, json_data: dict | None = None, text: str = ""):
        response = MagicMock(spec=httpx.Response)
        response.status_code = status_code
        response.text = text
        response.content = json_data is not None or text
        response.json.return_value = json_data
        return response
    return _create


class TestBaseServiceClient:
    """Tests for BaseServiceClient."""
    
    @pytest.mark.asyncio
    async def test_successful_get_request(self, client, mock_response):
        """Test successful GET request."""
        expected = {"id": 1, "name": "test"}
        
        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request.return_value = mock_response(200, expected)
            mock_get_client.return_value = mock_http_client
            
            result = await client.request("GET", "/api/test")
            
            assert result == expected
            mock_http_client.request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, client, mock_response):
        """Test retry logic on timeout."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            # First call times out, second succeeds
            mock_http_client.request.side_effect = [
                httpx.TimeoutException("timeout"),
                mock_response(200, {"success": True}),
            ]
            mock_get_client.return_value = mock_http_client
            
            # Should succeed after retry
            result = await client.request("GET", "/api/test")
            
            assert result == {"success": True}
            assert mock_http_client.request.call_count == 2
    
    @pytest.mark.asyncio
    async def test_no_retry_on_4xx(self, client, mock_response):
        """Test no retry on 4xx errors."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            response = mock_response(404, {"detail": "Not found"}, "Not found")
            mock_http_client.request.return_value = response
            mock_get_client.return_value = mock_http_client
            
            with pytest.raises(ServiceResponseError) as exc_info:
                await client.request("GET", "/api/test")
            
            assert exc_info.value.status_code == 404
            assert mock_http_client.request.call_count == 1  # No retry
    
    @pytest.mark.asyncio
    async def test_retry_on_5xx(self, client, mock_response):
        """Test retry on 5xx errors."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            error_response = mock_response(500, None, "Internal error")
            error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "500", request=MagicMock(), response=error_response
            )
            mock_http_client.request.return_value = error_response
            mock_get_client.return_value = mock_http_client
            
            with pytest.raises(httpx.HTTPStatusError):
                await client.request("GET", "/api/test")
            
            # Should have retried max_retries times
            assert mock_http_client.request.call_count == 3
    
    @pytest.mark.asyncio
    async def test_204_returns_none(self, client, mock_response):
        """Test 204 No Content returns None."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            response = mock_response(204)
            response.content = b""
            mock_http_client.request.return_value = response
            mock_get_client.return_value = mock_http_client
            
            result = await client.request("DELETE", "/api/test/1")
            
            assert result is None
    
    def test_normalize_endpoint_uuid(self, client):
        """Test UUID normalization in endpoints."""
        endpoint = "/api/assistants/550e8400-e29b-41d4-a716-446655440000"
        normalized = client._normalize_endpoint(endpoint)
        assert normalized == "/api/assistants/{id}"
    
    def test_normalize_endpoint_numeric(self, client):
        """Test numeric ID normalization in endpoints."""
        endpoint = "/api/users/123/messages/456"
        normalized = client._normalize_endpoint(endpoint)
        assert normalized == "/api/users/{id}/messages/{id}"
```

---

## Фаза 2: Миграция сервисов на единый клиент

**Срок:** 8-12 часов  
**Приоритет:** Высокий

### 2.1 Порядок миграции

| Приоритет | Сервис | Сложность | Риск | Причина приоритета |
|-----------|--------|-----------|------|-------------------|
| 1 | `cron_service` | Низкая | Высокий | Нет retry, синхронный, критичен для напоминаний |
| 2 | `rag_service` | Низкая | Средний | Простой клиент, мало методов |
| 3 | `google_calendar_service` | Низкая | Средний | Простой клиент |
| 4 | `admin_service` | Средняя | Низкий | Много методов, но не критичен |
| 5 | `telegram_bot_service` | Низкая | Средний | Inline вызовы, нужен рефакторинг |
| 6 | `assistant_service` | Высокая | Высокий | Самый большой клиент, много методов |

### 2.2 Миграция cron_service (приоритет 1)

**Текущий файл:** `cron_service/src/rest_client.py` (~250 строк, синхронный `requests`)

**Новый файл:** `cron_service/src/clients/rest_client.py`

```python
"""REST client for cron_service using BaseServiceClient."""

from datetime import datetime
from typing import Any
from uuid import UUID

from shared_models import BaseServiceClient, ClientConfig, get_logger

logger = get_logger(__name__)


class CronRestClient(BaseServiceClient):
    """REST client for cron_service."""
    
    def __init__(self, base_url: str):
        config = ClientConfig(
            timeout=30.0,
            max_retries=3,
            circuit_breaker_fail_max=5,
            circuit_breaker_reset_timeout=60.0,
        )
        super().__init__(
            base_url=base_url,
            service_name="cron_service",
            target_service="rest_service",
            config=config,
        )
    
    # === Reminders ===
    
    async def fetch_active_reminders(self) -> list[dict]:
        """Fetch active reminders for scheduling."""
        try:
            result = await self.request("GET", "/api/reminders/scheduled")
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error("Failed to fetch reminders", error=str(e))
            return []
    
    async def mark_reminder_completed(self, reminder_id: UUID) -> bool:
        """Mark reminder as completed."""
        try:
            await self.request(
                "PATCH",
                f"/api/reminders/{reminder_id}",
                json={"status": "completed"},
            )
            return True
        except Exception as e:
            logger.error("Failed to mark reminder completed", reminder_id=str(reminder_id), error=str(e))
            return False
    
    # === Global Settings ===
    
    async def fetch_global_settings(self) -> dict[str, Any] | None:
        """Fetch global settings."""
        try:
            return await self.request("GET", "/api/global-settings/")
        except Exception as e:
            logger.error("Failed to fetch global settings", error=str(e))
            return None
    
    # === Conversations ===
    
    async def fetch_conversations(
        self,
        since: datetime | None = None,
        user_id: int | None = None,
        min_messages: int = 2,
        limit: int = 50,
    ) -> list[dict]:
        """Fetch conversations for memory extraction."""
        try:
            params: dict[str, Any] = {"min_messages": min_messages, "limit": limit}
            if since:
                params["since"] = since.isoformat()
            if user_id:
                params["user_id"] = user_id
            
            result = await self.request("GET", "/api/conversations/", params=params)
            if isinstance(result, dict):
                return result.get("conversations", [])
            return []
        except Exception as e:
            logger.error("Failed to fetch conversations", error=str(e))
            return []
    
    # === Batch Jobs ===
    
    async def create_batch_job(
        self,
        batch_id: str,
        user_id: int,
        assistant_id: UUID | None = None,
        provider: str = "openai",
        model: str = "gpt-4o-mini",
        messages_processed: int = 0,
    ) -> dict | None:
        """Create batch job record."""
        try:
            payload = {
                "batch_id": batch_id,
                "user_id": user_id,
                "provider": provider,
                "model": model,
                "messages_processed": messages_processed,
            }
            if assistant_id:
                payload["assistant_id"] = str(assistant_id)
            
            return await self.request("POST", "/api/batch-jobs/", json=payload)
        except Exception as e:
            logger.error("Failed to create batch job", error=str(e))
            return None
    
    async def fetch_pending_batch_jobs(self, job_type: str = "memory_extraction") -> list[dict]:
        """Fetch pending batch jobs."""
        try:
            result = await self.request(
                "GET",
                "/api/batch-jobs/pending",
                params={"job_type": job_type},
            )
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error("Failed to fetch pending batch jobs", error=str(e))
            return []
    
    async def update_batch_job_status(
        self,
        job_id: UUID,
        status: str,
        facts_extracted: int | None = None,
        error_message: str | None = None,
    ) -> dict | None:
        """Update batch job status."""
        try:
            payload: dict[str, Any] = {"status": status}
            if facts_extracted is not None:
                payload["facts_extracted"] = facts_extracted
            if error_message is not None:
                payload["error_message"] = error_message
            
            return await self.request("PATCH", f"/api/batch-jobs/{job_id}", json=payload)
        except Exception as e:
            logger.error("Failed to update batch job", job_id=str(job_id), error=str(e))
            return None
    
    # === Job Executions ===
    
    async def create_job_execution(
        self,
        job_id: str,
        job_name: str,
        job_type: str,
        scheduled_at: datetime,
        user_id: int | None = None,
        reminder_id: int | None = None,
    ) -> dict | None:
        """Create job execution record."""
        try:
            payload: dict[str, Any] = {
                "job_id": job_id,
                "job_name": job_name,
                "job_type": job_type,
                "scheduled_at": scheduled_at.isoformat(),
            }
            if user_id is not None:
                payload["user_id"] = user_id
            if reminder_id is not None:
                payload["reminder_id"] = reminder_id
            
            return await self.request("POST", "/api/job-executions/", json=payload)
        except Exception as e:
            logger.error("Failed to create job execution", error=str(e))
            return None
    
    async def start_job_execution(self, execution_id: str) -> dict | None:
        """Mark job execution as started."""
        try:
            return await self.request("PATCH", f"/api/job-executions/{execution_id}/start")
        except Exception as e:
            logger.error("Failed to start job execution", execution_id=execution_id, error=str(e))
            return None
    
    async def complete_job_execution(self, execution_id: str, result: str | None = None) -> dict | None:
        """Mark job execution as completed."""
        try:
            payload = {"result": result} if result else None
            return await self.request(
                "PATCH",
                f"/api/job-executions/{execution_id}/complete",
                json=payload,
            )
        except Exception as e:
            logger.error("Failed to complete job execution", execution_id=execution_id, error=str(e))
            return None
    
    async def fail_job_execution(
        self,
        execution_id: str,
        error: str,
        error_traceback: str | None = None,
    ) -> dict | None:
        """Mark job execution as failed."""
        try:
            payload: dict[str, Any] = {"error": error}
            if error_traceback:
                payload["error_traceback"] = error_traceback
            
            return await self.request(
                "PATCH",
                f"/api/job-executions/{execution_id}/fail",
                json=payload,
            )
        except Exception as e:
            logger.error("Failed to fail job execution", execution_id=execution_id, error=str(e))
            return None


# Singleton instance
_client: CronRestClient | None = None


async def get_rest_client() -> CronRestClient:
    """Get or create REST client singleton."""
    global _client
    if _client is None:
        import os
        base_url = os.getenv("REST_SERVICE_URL", "http://rest_service:8000")
        _client = CronRestClient(base_url)
    return _client
```

**Изменения в scheduler.py:**
- Заменить синхронные вызовы на async
- Использовать `asyncio.run()` в APScheduler jobs или перейти на async scheduler

### 2.3 Миграция остальных сервисов

Аналогичный подход для каждого сервиса:

1. Создать класс-наследник `BaseServiceClient`
2. Перенести методы из старого клиента
3. Обновить вызовы в коде сервиса
4. Удалить старый клиент
5. Обновить тесты

**Детальные файлы для каждого сервиса будут созданы в процессе миграции.**

---

## Фаза 3: Вынос операций в Redis

**Срок:** 6-8 часов  
**Приоритет:** Средний

### 3.1 Кандидаты для Redis Cache

| Данные | Текущий источник | TTL | Причина |
|--------|------------------|-----|---------|
| Global Settings | REST API | 5 мин | Читается при каждом запросе assistant |
| Assistant Config | REST API | 5 мин | Читается при каждом сообщении |
| User Secretary Link | REST API | 5 мин | Читается при каждом сообщении |
| Tools List | REST API | 5 мин | Читается при инициализации assistant |

### 3.2 Реализация Redis Cache

**Файл:** `shared_models/src/shared_models/cache.py`

```python
"""Redis cache wrapper with TTL and invalidation support."""

import json
from typing import Any, TypeVar, Generic
from datetime import timedelta

import redis.asyncio as redis
from pydantic import BaseModel

from shared_models.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class RedisCache:
    """Redis cache with typed get/set and Pub/Sub invalidation."""
    
    INVALIDATION_CHANNEL = "cache:invalidation"
    
    def __init__(self, redis_client: redis.Redis, prefix: str = "cache"):
        self.redis = redis_client
        self.prefix = prefix
        self._pubsub: redis.client.PubSub | None = None
    
    def _key(self, key: str) -> str:
        """Build full cache key."""
        return f"{self.prefix}:{key}"
    
    async def get(self, key: str, model_class: type[T]) -> T | None:
        """Get cached value and deserialize to Pydantic model."""
        full_key = self._key(key)
        try:
            data = await self.redis.get(full_key)
            if data is None:
                return None
            return model_class.model_validate_json(data)
        except Exception as e:
            logger.warning("Cache get failed", key=key, error=str(e))
            return None
    
    async def get_raw(self, key: str) -> dict | list | None:
        """Get cached value as raw dict/list."""
        full_key = self._key(key)
        try:
            data = await self.redis.get(full_key)
            if data is None:
                return None
            return json.loads(data)
        except Exception as e:
            logger.warning("Cache get_raw failed", key=key, error=str(e))
            return None
    
    async def set(
        self,
        key: str,
        value: BaseModel | dict | list,
        ttl: timedelta | int = 300,
    ) -> bool:
        """Set cached value with TTL."""
        full_key = self._key(key)
        try:
            if isinstance(value, BaseModel):
                data = value.model_dump_json()
            else:
                data = json.dumps(value)
            
            ttl_seconds = ttl.total_seconds() if isinstance(ttl, timedelta) else ttl
            await self.redis.setex(full_key, int(ttl_seconds), data)
            return True
        except Exception as e:
            logger.warning("Cache set failed", key=key, error=str(e))
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete cached value."""
        full_key = self._key(key)
        try:
            await self.redis.delete(full_key)
            return True
        except Exception as e:
            logger.warning("Cache delete failed", key=key, error=str(e))
            return False
    
    async def invalidate(self, pattern: str) -> int:
        """Invalidate all keys matching pattern and notify subscribers."""
        full_pattern = self._key(pattern)
        try:
            keys = []
            async for key in self.redis.scan_iter(match=full_pattern):
                keys.append(key)
            
            if keys:
                await self.redis.delete(*keys)
                # Publish invalidation event
                await self.redis.publish(
                    self.INVALIDATION_CHANNEL,
                    json.dumps({"pattern": pattern, "keys_deleted": len(keys)}),
                )
            
            logger.info("Cache invalidated", pattern=pattern, keys_deleted=len(keys))
            return len(keys)
        except Exception as e:
            logger.warning("Cache invalidate failed", pattern=pattern, error=str(e))
            return 0
    
    async def subscribe_invalidation(self, callback) -> None:
        """Subscribe to cache invalidation events."""
        self._pubsub = self.redis.pubsub()
        await self._pubsub.subscribe(self.INVALIDATION_CHANNEL)
        
        async for message in self._pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await callback(data)
                except Exception as e:
                    logger.warning("Invalidation callback failed", error=str(e))
```

### 3.3 Интеграция кэша в rest_service

**Файл:** `rest_service/src/middleware/cache_invalidation.py`

```python
"""Middleware for cache invalidation on data changes."""

import redis.asyncio as redis
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from shared_models.cache import RedisCache


class CacheInvalidationMiddleware(BaseHTTPMiddleware):
    """Invalidate cache on mutating operations."""
    
    INVALIDATION_RULES = {
        # (method, path_prefix): cache_pattern
        ("POST", "/api/assistants"): "assistant:*",
        ("PUT", "/api/assistants"): "assistant:*",
        ("DELETE", "/api/assistants"): "assistant:*",
        ("POST", "/api/tools"): "tools:*",
        ("PUT", "/api/tools"): "tools:*",
        ("DELETE", "/api/tools"): "tools:*",
        ("PUT", "/api/global-settings"): "settings:*",
        ("POST", "/api/users"): "user:*",
        ("PUT", "/api/users"): "user:*",
        ("POST", "/api/user-secretaries"): "secretary:*",
        ("DELETE", "/api/user-secretaries"): "secretary:*",
    }
    
    def __init__(self, app, redis_client: redis.Redis):
        super().__init__(app)
        self.cache = RedisCache(redis_client, prefix="api_cache")
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Only invalidate on successful mutating operations
        if response.status_code < 300:
            await self._maybe_invalidate(request.method, request.url.path)
        
        return response
    
    async def _maybe_invalidate(self, method: str, path: str) -> None:
        """Check if cache should be invalidated."""
        for (rule_method, rule_prefix), pattern in self.INVALIDATION_RULES.items():
            if method == rule_method and path.startswith(rule_prefix):
                await self.cache.invalidate(pattern)
                break
```

### 3.4 Кэширование в assistant_service

**Обновление AssistantFactory для использования кэша:**

```python
# В assistant_service/src/assistants/factory.py

class AssistantFactory:
    def __init__(self, settings: Settings, redis_client: redis.Redis):
        self.settings = settings
        self.cache = RedisCache(redis_client, prefix="assistant_cache")
        self.rest_client = RestServiceClient()
        # ...
    
    async def get_global_settings(self) -> GlobalSettingsBase:
        """Get global settings with caching."""
        cache_key = "global_settings"
        
        # Try cache first
        cached = await self.cache.get_raw(cache_key)
        if cached:
            return GlobalSettingsBase(**cached)
        
        # Fetch from REST
        settings = await self.rest_client.get_global_settings()
        
        # Cache for 5 minutes
        await self.cache.set(cache_key, settings.model_dump(), ttl=300)
        
        return settings
    
    async def get_user_secretary(self, user_id: int) -> AssistantRead | None:
        """Get user's secretary with caching."""
        cache_key = f"secretary:{user_id}"
        
        # Try cache first
        cached = await self.cache.get(cache_key, AssistantRead)
        if cached:
            return cached
        
        # Fetch from REST
        secretary = await self.rest_client.get_user_secretary(user_id)
        if secretary:
            await self.cache.set(cache_key, secretary, ttl=300)
        
        return secretary
```

---

## Фаза 4: Мониторинг и дашборды

**Срок:** 4-6 часов  
**Приоритет:** Высокий

### 4.1 Метрики для сбора

| Метрика | Тип | Labels | Описание |
|---------|-----|--------|----------|
| `http_client_requests_total` | Counter | service, method, endpoint, status | Всего HTTP запросов |
| `http_client_request_duration_seconds` | Histogram | service, method, endpoint | Время выполнения запросов |
| `http_client_retries_total` | Counter | service, method, endpoint, error_type | Количество retry |
| `http_client_circuit_breaker_state` | Gauge | service, target_service | Состояние circuit breaker |
| `redis_cache_hits_total` | Counter | cache_name, key_pattern | Попадания в кэш |
| `redis_cache_misses_total` | Counter | cache_name, key_pattern | Промахи кэша |
| `redis_cache_operations_duration_seconds` | Histogram | cache_name, operation | Время операций с кэшем |

### 4.2 Grafana Dashboard: Service Communication

**Файл:** `monitoring/grafana/provisioning/dashboards/service_communication.json`

```json
{
  "title": "Service Communication",
  "uid": "service-communication",
  "tags": ["microservices", "http", "redis"],
  "panels": [
    {
      "title": "HTTP Requests Rate by Service",
      "type": "timeseries",
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
      "targets": [
        {
          "expr": "sum(rate(http_client_requests_total[5m])) by (service, target_service)",
          "legendFormat": "{{service}} → {{target_service}}"
        }
      ]
    },
    {
      "title": "HTTP Request Duration (p95)",
      "type": "timeseries",
      "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
      "targets": [
        {
          "expr": "histogram_quantile(0.95, sum(rate(http_client_request_duration_seconds_bucket[5m])) by (service, le))",
          "legendFormat": "{{service}} p95"
        }
      ]
    },
    {
      "title": "Error Rate by Service",
      "type": "timeseries",
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
      "targets": [
        {
          "expr": "sum(rate(http_client_requests_total{status!=\"success\"}[5m])) by (service, status)",
          "legendFormat": "{{service}} - {{status}}"
        }
      ]
    },
    {
      "title": "Retry Rate",
      "type": "timeseries",
      "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
      "targets": [
        {
          "expr": "sum(rate(http_client_retries_total[5m])) by (service, error_type)",
          "legendFormat": "{{service}} - {{error_type}}"
        }
      ]
    },
    {
      "title": "Circuit Breaker State",
      "type": "stat",
      "gridPos": {"h": 4, "w": 24, "x": 0, "y": 16},
      "targets": [
        {
          "expr": "http_client_circuit_breaker_state",
          "legendFormat": "{{service}} → {{target_service}}"
        }
      ],
      "options": {
        "colorMode": "value",
        "graphMode": "none"
      },
      "fieldConfig": {
        "defaults": {
          "mappings": [
            {"type": "value", "options": {"0": {"text": "CLOSED", "color": "green"}}},
            {"type": "value", "options": {"1": {"text": "OPEN", "color": "red"}}},
            {"type": "value", "options": {"2": {"text": "HALF-OPEN", "color": "yellow"}}}
          ]
        }
      }
    },
    {
      "title": "Cache Hit Rate",
      "type": "gauge",
      "gridPos": {"h": 8, "w": 8, "x": 0, "y": 20},
      "targets": [
        {
          "expr": "sum(rate(redis_cache_hits_total[5m])) / (sum(rate(redis_cache_hits_total[5m])) + sum(rate(redis_cache_misses_total[5m])))",
          "legendFormat": "Hit Rate"
        }
      ],
      "options": {
        "reduceOptions": {"calcs": ["lastNotNull"]}
      },
      "fieldConfig": {
        "defaults": {
          "min": 0,
          "max": 1,
          "unit": "percentunit",
          "thresholds": {
            "steps": [
              {"color": "red", "value": 0},
              {"color": "yellow", "value": 0.7},
              {"color": "green", "value": 0.9}
            ]
          }
        }
      }
    },
    {
      "title": "Top Endpoints by Request Count",
      "type": "table",
      "gridPos": {"h": 8, "w": 16, "x": 8, "y": 20},
      "targets": [
        {
          "expr": "topk(10, sum(increase(http_client_requests_total[1h])) by (service, endpoint))",
          "format": "table",
          "instant": true
        }
      ]
    }
  ]
}
```

### 4.3 Алерты

**Файл:** `monitoring/grafana/provisioning/alerting/service_communication_rules.yml`

```yaml
apiVersion: 1
groups:
  - orgId: 1
    name: Service Communication
    folder: Alerts
    interval: 1m
    rules:
      - uid: circuit-breaker-open
        title: Circuit Breaker Open
        condition: C
        data:
          - refId: A
            relativeTimeRange:
              from: 300
              to: 0
            datasourceUid: prometheus
            model:
              expr: http_client_circuit_breaker_state == 1
              instant: true
        for: 1m
        annotations:
          summary: "Circuit breaker open: {{ $labels.service }} → {{ $labels.target_service }}"
          description: "Service communication is blocked due to repeated failures"
        labels:
          severity: critical
      
      - uid: high-error-rate
        title: High HTTP Error Rate
        condition: C
        data:
          - refId: A
            relativeTimeRange:
              from: 300
              to: 0
            datasourceUid: prometheus
            model:
              expr: |
                sum(rate(http_client_requests_total{status!="success"}[5m])) by (service)
                / sum(rate(http_client_requests_total[5m])) by (service) > 0.1
              instant: true
        for: 5m
        annotations:
          summary: "High error rate for {{ $labels.service }}"
          description: "More than 10% of HTTP requests are failing"
        labels:
          severity: warning
      
      - uid: high-retry-rate
        title: High Retry Rate
        condition: C
        data:
          - refId: A
            relativeTimeRange:
              from: 300
              to: 0
            datasourceUid: prometheus
            model:
              expr: |
                sum(rate(http_client_retries_total[5m])) by (service) > 1
              instant: true
        for: 5m
        annotations:
          summary: "High retry rate for {{ $labels.service }}"
          description: "Service is experiencing connectivity issues"
        labels:
          severity: warning
      
      - uid: low-cache-hit-rate
        title: Low Cache Hit Rate
        condition: C
        data:
          - refId: A
            relativeTimeRange:
              from: 600
              to: 0
            datasourceUid: prometheus
            model:
              expr: |
                sum(rate(redis_cache_hits_total[10m])) 
                / (sum(rate(redis_cache_hits_total[10m])) + sum(rate(redis_cache_misses_total[10m]))) < 0.5
              instant: true
        for: 10m
        annotations:
          summary: "Low cache hit rate"
          description: "Cache is not being utilized effectively"
        labels:
          severity: info
```

---

## Фаза 5: Тестирование

**Срок:** 6-8 часов  
**Приоритет:** Высокий

### 5.1 Структура тестов

```
tests/
├── unit/
│   └── shared_models/
│       ├── test_http_client.py      # BaseServiceClient
│       └── test_cache.py            # RedisCache
├── integration/
│   ├── test_service_communication.py  # HTTP между сервисами
│   └── test_cache_invalidation.py     # Redis cache + Pub/Sub
```

### 5.2 Unit-тесты (по сервисам)

| Сервис | Тестовый файл | Покрытие |
|--------|---------------|----------|
| `shared_models` | `test_http_client.py` | Retry, circuit breaker, metrics, errors |
| `shared_models` | `test_cache.py` | Get/set, TTL, invalidation, Pub/Sub |
| `cron_service` | `test_rest_client.py` | Все методы CronRestClient |
| `assistant_service` | `test_rest_service.py` | Обновить существующие тесты |
| `admin_service` | `test_rest_client.py` | Обновить существующие тесты |

### 5.3 Integration-тесты

**Файл:** `tests/integration/test_service_communication.py`

```python
"""Integration tests for service communication."""

import pytest
import asyncio
from unittest.mock import patch

import httpx
from testcontainers.compose import DockerCompose


@pytest.fixture(scope="module")
def compose():
    """Start docker-compose with rest_service and redis."""
    with DockerCompose(
        filepath=".",
        compose_file_name="docker-compose.integration.yml",
        pull=True,
    ) as compose:
        compose.wait_for("rest_service")
        compose.wait_for("redis")
        yield compose


class TestServiceCommunication:
    """Test HTTP communication between services."""
    
    @pytest.mark.asyncio
    async def test_assistant_to_rest_communication(self, compose):
        """Test assistant_service can communicate with rest_service."""
        from assistant_service.src.services.rest_service import RestServiceClient
        
        async with RestServiceClient() as client:
            # Should successfully fetch users
            users = await client.get_users()
            assert isinstance(users, list)
    
    @pytest.mark.asyncio
    async def test_retry_on_temporary_failure(self, compose):
        """Test retry logic when rest_service temporarily unavailable."""
        from shared_models import BaseServiceClient
        
        class TestClient(BaseServiceClient):
            def __init__(self):
                super().__init__(
                    base_url="http://rest_service:8000",
                    service_name="test",
                    target_service="rest_service",
                )
        
        async with TestClient() as client:
            # Mock first request to fail, second to succeed
            with patch.object(
                client,
                "_execute_request",
                side_effect=[
                    httpx.ConnectError("connection refused"),
                    {"status": "ok"},
                ],
            ):
                result = await client.request("GET", "/health")
                assert result == {"status": "ok"}
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_failures(self, compose):
        """Test circuit breaker opens after repeated failures."""
        from shared_models import BaseServiceClient, ServiceUnavailableError
        
        class TestClient(BaseServiceClient):
            def __init__(self):
                super().__init__(
                    base_url="http://nonexistent:8000",
                    service_name="test",
                    target_service="nonexistent",
                )
        
        async with TestClient() as client:
            # Make enough requests to trip circuit breaker
            for _ in range(6):
                try:
                    await client.request("GET", "/api/test")
                except Exception:
                    pass
            
            # Next request should fail with circuit breaker error
            with pytest.raises(ServiceUnavailableError):
                await client.request("GET", "/api/test")


class TestCacheInvalidation:
    """Test Redis cache and invalidation."""
    
    @pytest.mark.asyncio
    async def test_cache_hit_after_set(self, compose):
        """Test cache returns value after set."""
        import redis.asyncio as redis
        from shared_models.cache import RedisCache
        from pydantic import BaseModel
        
        class TestModel(BaseModel):
            id: int
            name: str
        
        client = redis.Redis(host="localhost", port=6379, db=0)
        cache = RedisCache(client, prefix="test")
        
        model = TestModel(id=1, name="test")
        await cache.set("test_key", model, ttl=60)
        
        result = await cache.get("test_key", TestModel)
        assert result == model
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_invalidation_deletes_keys(self, compose):
        """Test invalidation removes matching keys."""
        import redis.asyncio as redis
        from shared_models.cache import RedisCache
        
        client = redis.Redis(host="localhost", port=6379, db=0)
        cache = RedisCache(client, prefix="test")
        
        # Set multiple keys
        await cache.set("user:1", {"id": 1}, ttl=60)
        await cache.set("user:2", {"id": 2}, ttl=60)
        await cache.set("other:1", {"id": 1}, ttl=60)
        
        # Invalidate user:* pattern
        deleted = await cache.invalidate("user:*")
        
        assert deleted == 2
        assert await cache.get_raw("user:1") is None
        assert await cache.get_raw("user:2") is None
        assert await cache.get_raw("other:1") is not None
        
        await client.close()
```

### 5.4 Обновление CI/CD

**Добавить в `.github/workflows/ci.yml`:**

```yaml
  integration-communication-tests:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      
      - name: Build test base image
        run: make build-test-base
      
      - name: Run communication integration tests
        run: |
          docker-compose -f docker-compose.integration.yml up -d db redis rest_service
          sleep 10  # Wait for services
          docker-compose -f docker-compose.integration.yml run --rm test_runner \
            pytest tests/integration/test_service_communication.py -v
          docker-compose -f docker-compose.integration.yml down
```

---

## Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Breaking changes в API клиентов | Высокая | Среднее | Постепенная миграция, сохранение обратной совместимости |
| Проблемы с async в cron_service | Средняя | Высокое | Использовать asyncio.run() в job handlers |
| Circuit breaker блокирует легитимные запросы | Низкая | Высокое | Настроить правильные thresholds, мониторинг |
| Рост latency из-за Redis cache | Низкая | Низкое | Мониторинг, fallback на REST при проблемах с Redis |
| Сложность отладки | Средняя | Среднее | Structured logging, correlation_id, дашборды |

---

## Чеклист готовности

### Фаза 1: BaseServiceClient
- [x] Создан `shared_models/src/shared_models/http_client.py`
- [x] Добавлены зависимости в `shared_models/pyproject.toml`
- [x] Unit-тесты для BaseServiceClient
- [x] Документация в docstrings

### Фаза 2: Миграция сервисов
- [x] `cron_service` мигрирован
- [x] `rag_service` мигрирован
- [x] `google_calendar_service` мигрирован
- [x] `admin_service` мигрирован
- [x] `telegram_bot_service` мигрирован
- [x] `assistant_service` мигрирован
- [ ] Старые клиенты удалены

### Фаза 3: Redis Cache
- [x] Создан `shared_models/src/shared_models/cache.py`
- [x] Middleware для инвалидации в `rest_service`
- [x] Кэширование в `assistant_service`
- [x] Unit-тесты для RedisCache

### Фаза 4: Мониторинг
- [ ] Dashboard "Service Communication" создан
- [ ] Алерты настроены
- [ ] Метрики проверены в Prometheus

### Фаза 5: Тестирование
- [ ] Unit-тесты для всех новых компонентов
- [ ] Integration-тесты для коммуникации
- [ ] CI/CD обновлен
- [ ] Все тесты проходят

---

## Оценка трудозатрат

| Фаза | Часы | Зависимости |
|------|------|-------------|
| Фаза 1: BaseServiceClient | 4-6 | - |
| Фаза 2: Миграция сервисов | 8-12 | Фаза 1 |
| Фаза 3: Redis Cache | 6-8 | Фаза 1 |
| Фаза 4: Мониторинг | 4-6 | Фаза 1, 2 |
| Фаза 5: Тестирование | 6-8 | Фаза 1, 2, 3 |
| **Итого** | **28-40** | |

**Рекомендуемый порядок:** 1 → 2 (cron) → 4 → 2 (остальные) → 3 → 5
