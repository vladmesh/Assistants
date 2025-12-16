# Dead Letter Queue (DLQ) Implementation Plan

**Дата**: 2024-12-16  
**Приоритет**: КРИТИЧНО  
**Ожидаемый эффект**: снижение потери сообщений с ~1-5% до <0.1%

## Обзор проблемы

В текущей реализации `assistant_service/src/orchestrator.py` сообщения всегда ACK-аются в блоке `finally` (строки 597-613), независимо от результата обработки:

```python
finally:
    if stream_message_id and not acked:
        try:
            await self.input_stream.ack(stream_message_id)
            acked = True
        except Exception as ack_exc:
            logger.error(...)
```

Это приводит к потере сообщений при ошибках обработки.

## Архитектура решения

```
                                    ┌──────────────────┐
                                    │   DLQ Stream     │
                                    │ {queue}:dlq      │
                                    └────────▲─────────┘
                                             │
                                             │ (retry_count >= MAX)
┌─────────────┐    ┌─────────────┐    ┌──────┴──────┐    ┌─────────────┐
│ Input Queue │───▶│ Orchestrator│───▶│  Dispatch   │───▶│Output Queue │
│  (Redis)    │    │             │    │  Event      │    │  (Redis)    │
└─────────────┘    └─────────────┘    └──────┬──────┘    └─────────────┘
       ▲                                     │
       │         (retry_count < MAX)         │
       └─────────────────────────────────────┘
                   xautoclaim
```

---

## Итерация 1: Расширение RedisStreamClient

**Цель**: Добавить методы для работы с retry-счетчиком и DLQ

**Файл**: `assistant_service/src/services/redis_stream.py`

### 1.1 Добавить константы

```python
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]  # seconds (exponential backoff)
DLQ_SUFFIX = ":dlq"
```

### 1.2 Добавить методы для retry-счетчика

```python
@staticmethod
def get_retry_count(message_fields: dict) -> int:
    """Extract retry count from message fields."""
    retry_count = message_fields.get("retry_count") or message_fields.get(b"retry_count")
    if retry_count is None:
        return 0
    if isinstance(retry_count, bytes):
        retry_count = retry_count.decode("utf-8")
    return int(retry_count)

async def increment_retry_count(self, message_id: str, current_count: int) -> None:
    """Increment retry count in message metadata (via re-add with updated count)."""
    # Note: Redis Streams don't support field updates, 
    # we'll track retries separately or via message re-queue
    pass
```

### 1.3 Добавить метод для DLQ

```python
@property
def dlq_stream(self) -> str:
    """Return DLQ stream name."""
    return f"{self.stream}{DLQ_SUFFIX}"

async def send_to_dlq(
    self,
    original_message_id: str,
    payload: bytes | str,
    error_info: dict,
    retry_count: int,
) -> str:
    """Send failed message to Dead Letter Queue."""
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    
    dlq_entry = {
        "payload": payload,
        "original_message_id": original_message_id,
        "error_type": error_info.get("error_type", "unknown"),
        "error_message": error_info.get("error_message", ""),
        "retry_count": str(retry_count),
        "failed_at": datetime.now(UTC).isoformat(),
        "user_id": error_info.get("user_id", ""),
    }
    
    return await self.client.xadd(self.dlq_stream, dlq_entry)
```

### 1.4 Добавить метод для получения задержки retry

```python
def get_retry_delay(self, retry_count: int) -> int:
    """Get delay in seconds before next retry (exponential backoff)."""
    if retry_count >= len(RETRY_DELAYS):
        return RETRY_DELAYS[-1]
    return RETRY_DELAYS[retry_count]
```

### 1.5 Добавить методы для работы с DLQ

```python
async def read_dlq(
    self, count: int = 10, start_id: str = "0-0"
) -> list[tuple[str, dict]]:
    """Read messages from DLQ."""
    entries = await self.client.xrange(self.dlq_stream, min=start_id, count=count)
    return entries

async def delete_from_dlq(self, message_id: str) -> int:
    """Delete message from DLQ."""
    return await self.client.xdel(self.dlq_stream, message_id)

async def get_dlq_length(self) -> int:
    """Get number of messages in DLQ."""
    try:
        return await self.client.xlen(self.dlq_stream)
    except Exception:
        return 0

async def requeue_from_dlq(self, dlq_message_id: str) -> str | None:
    """Move message from DLQ back to main queue for retry."""
    entries = await self.client.xrange(
        self.dlq_stream, min=dlq_message_id, max=dlq_message_id, count=1
    )
    if not entries:
        return None
    
    _, fields = entries[0]
    payload = fields.get(b"payload") or fields.get("payload")
    
    # Add back to main stream
    new_id = await self.add(payload)
    
    # Delete from DLQ
    await self.delete_from_dlq(dlq_message_id)
    
    return new_id
```

### Чек-лист итерации 1 (ВЫПОЛНЕНО 2024-12-16)

- [x] Добавить константы `MAX_RETRIES`, `RETRY_DELAYS`, `DLQ_SUFFIX`
- [x] Реализовать `get_retry_count()`
- [x] Реализовать `dlq_stream` property
- [x] Реализовать `send_to_dlq()`
- [x] Реализовать `get_retry_delay()`
- [x] Реализовать `read_dlq()`
- [x] Реализовать `delete_from_dlq()`
- [x] Реализовать `get_dlq_length()`
- [x] Реализовать `requeue_from_dlq()`
- [x] Написать unit-тесты для новых методов (29 тестов, все прошли)

---

## Итерация 2: Модификация Orchestrator

**Цель**: Изменить логику ACK - только при успехе, при ошибках retry или DLQ

**Файл**: `assistant_service/src/orchestrator.py`

### 2.1 Добавить импорты и инициализацию

```python
from services.redis_stream import MAX_RETRIES, RedisStreamClient
```

### 2.2 Добавить хранение retry_count в памяти

Так как Redis Streams не поддерживают обновление полей, будем отслеживать retry через отдельный Redis ключ:

```python
async def _get_message_retry_count(self, message_id: str) -> int:
    """Get retry count for a message from Redis."""
    key = f"msg_retry:{message_id}"
    count = await self.redis.get(key)
    return int(count) if count else 0

async def _increment_message_retry_count(self, message_id: str) -> int:
    """Increment and return new retry count."""
    key = f"msg_retry:{message_id}"
    new_count = await self.redis.incr(key)
    await self.redis.expire(key, 3600)  # TTL 1 hour
    return new_count

async def _clear_message_retry_count(self, message_id: str) -> None:
    """Clear retry count after successful processing or DLQ."""
    key = f"msg_retry:{message_id}"
    await self.redis.delete(key)
```

### 2.3 Модифицировать `listen_for_messages()`

**Ключевые изменения**:

1. Убрать безусловный ACK из `finally`
2. ACK только при успешной обработке (`status == "success"`)
3. При ошибке - проверить retry_count:
   - Если < MAX_RETRIES: не ACK, сообщение останется в pending для xautoclaim
   - Если >= MAX_RETRIES: отправить в DLQ, затем ACK
4. Очищать retry_count после успеха или DLQ

```python
async def listen_for_messages(self):
    """Listen for messages/triggers from Redis and dispatch."""
    # ... existing setup code ...
    
    while True:
        raw_message_bytes = None
        response_payload = None
        event_object: QueueMessage | QueueTrigger | None = None
        stream_message_id: str | None = None
        should_ack = False
        processing_error: Exception | None = None

        try:
            stream_entry = await self.input_stream.read()
            if not stream_entry:
                continue

            stream_message_id, message_fields = stream_entry
            
            # Get current retry count
            retry_count = await self._get_message_retry_count(stream_message_id)
            
            # ... existing parsing logic ...
            
            if event_object:
                response_payload = await self._dispatch_event(event_object)
                
                # Check if processing was successful
                if response_payload and response_payload.get("status") == "success":
                    should_ack = True
                    await self._clear_message_retry_count(stream_message_id)
                else:
                    # Processing failed - handle retry or DLQ
                    processing_error = Exception(
                        response_payload.get("error", "Unknown error")
                    )
            
            # ... existing response sending logic ...

        except ConnectionError as e:
            logger.error(f"Redis connection error: {e}")
            await asyncio.sleep(5)
            continue
        except Exception as e:
            processing_error = e
            logger.error(f"Error in message listener loop: {e}", exc_info=True)

        finally:
            if stream_message_id:
                if should_ack:
                    # Success - ACK the message
                    try:
                        await self.input_stream.ack(stream_message_id)
                    except Exception as ack_exc:
                        logger.error("Failed to ACK message", error=str(ack_exc))
                elif processing_error:
                    # Failure - check retry count
                    await self._handle_processing_failure(
                        stream_message_id,
                        raw_message_bytes,
                        processing_error,
                        event_object,
                    )
```

### 2.4 Добавить метод обработки ошибок

```python
async def _handle_processing_failure(
    self,
    message_id: str,
    raw_payload: bytes | None,
    error: Exception,
    event: QueueMessage | QueueTrigger | None,
) -> None:
    """Handle message processing failure - retry or send to DLQ."""
    retry_count = await self._increment_message_retry_count(message_id)
    
    user_id = getattr(event, "user_id", "unknown") if event else "unknown"
    error_type = type(error).__name__
    
    if retry_count >= MAX_RETRIES:
        # Max retries exceeded - send to DLQ
        logger.warning(
            "Max retries exceeded, sending to DLQ",
            message_id=message_id,
            retry_count=retry_count,
            error_type=error_type,
            user_id=user_id,
        )
        
        error_info = {
            "error_type": error_type,
            "error_message": str(error),
            "user_id": str(user_id),
        }
        
        try:
            await self.input_stream.send_to_dlq(
                original_message_id=message_id,
                payload=raw_payload or b"",
                error_info=error_info,
                retry_count=retry_count,
            )
            # After DLQ, ACK original message
            await self.input_stream.ack(message_id)
            await self._clear_message_retry_count(message_id)
            
            # Update metrics
            messages_dlq_total.labels(
                error_type=error_type,
                queue=self.settings.INPUT_QUEUE,
            ).inc()
        except Exception as dlq_exc:
            logger.error(
                "Failed to send to DLQ",
                error=str(dlq_exc),
                message_id=message_id,
            )
    else:
        # Will be retried via xautoclaim
        delay = self.input_stream.get_retry_delay(retry_count - 1)
        logger.info(
            "Message will be retried",
            message_id=message_id,
            retry_count=retry_count,
            delay_seconds=delay,
            error_type=error_type,
        )
        
        # Update metrics
        message_processing_retries_total.labels(
            queue=self.settings.INPUT_QUEUE
        ).inc()
        
        # Don't ACK - message stays in pending list
        # Will be reclaimed after idle_reclaim_ms by xautoclaim
```

### Чек-лист итерации 2 (ВЫПОЛНЕНО 2024-12-16)

- [x] Добавить методы `_get_message_retry_count()`, `_increment_message_retry_count()`, `_clear_message_retry_count()`
- [x] Модифицировать `listen_for_messages()` - убрать безусловный ACK
- [x] Добавить логику проверки `status == "success"` для ACK
- [x] Реализовать `_handle_processing_failure()`
- [x] Добавить структурированное логирование retry/DLQ событий
- [ ] Протестировать вручную с имитацией ошибок (отложено до интеграции)
- [x] Написать unit-тесты (11 тестов для retry логики)

---

## Итерация 3: Prometheus метрики

**Цель**: Добавить метрики для мониторинга DLQ и retry

**Файл**: `assistant_service/src/metrics.py`

### 3.1 Добавить новые метрики

```python
# DLQ metrics
messages_dlq_total = Counter(
    "messages_dlq_total",
    "Total messages sent to Dead Letter Queue",
    ["error_type", "queue"],
)

message_processing_retries_total = Counter(
    "message_processing_retries_total",
    "Total message processing retry attempts",
    ["queue"],
)

dlq_size = Gauge(
    "dlq_size",
    "Current number of messages in Dead Letter Queue",
    ["queue"],
)

message_retry_count_histogram = Histogram(
    "message_retry_count",
    "Distribution of retry counts before success or DLQ",
    ["queue", "outcome"],  # outcome: success, dlq
    buckets=[0, 1, 2, 3, 4, 5],
)
```

### 3.2 Обновить существующие метрики

Добавить label `status` в `messages_processed_total`:
- `success` - успешная обработка
- `error` - ошибка (retry или DLQ)
- `dlq` - отправлено в DLQ

### 3.3 Добавить периодическое обновление dlq_size

```python
async def update_dlq_metrics(input_stream: RedisStreamClient, interval: int = 60):
    """Periodically update DLQ size gauge."""
    while True:
        try:
            size = await input_stream.get_dlq_length()
            dlq_size.labels(queue=input_stream.stream).set(size)
        except Exception as e:
            logger.warning(f"Failed to update DLQ metrics: {e}")
        await asyncio.sleep(interval)
```

### Чек-лист итерации 3 (ВЫПОЛНЕНО 2024-12-16)

- [x] Добавить `messages_dlq_total` Counter
- [x] Добавить `message_processing_retries_total` Counter
- [x] Добавить `dlq_size` Gauge
- [x] Добавить `message_retry_count_histogram` Histogram
- [x] Реализовать `update_dlq_metrics()` корутину
- [x] Запустить корутину в `main.py`
- [x] Интегрировать метрики в orchestrator._handle_processing_failure()
- [ ] Проверить метрики в Prometheus/Grafana (отложено до деплоя)

---

## Итерация 4: REST API для управления DLQ

**Цель**: Создать эндпоинты для просмотра и управления DLQ

**Файлы**:
- `rest_service/src/routers/dlq.py` (новый)
- `rest_service/src/models/dlq.py` (новый)
- `rest_service/src/main.py` (обновить)

### 4.1 Создать модели

```python
# rest_service/src/models/dlq.py
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DLQMessageResponse(BaseModel):
    """DLQ message response."""
    
    message_id: str
    original_message_id: str
    payload: str
    error_type: str
    error_message: str
    retry_count: int
    failed_at: datetime
    user_id: str | None


class DLQStatsResponse(BaseModel):
    """DLQ statistics."""
    
    queue_name: str
    total_messages: int
    by_error_type: dict[str, int]
    oldest_message_at: datetime | None
    newest_message_at: datetime | None
```

### 4.2 Создать роутер

```python
# rest_service/src/routers/dlq.py
from datetime import UTC, datetime
from typing import Annotated

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from config import Settings, get_settings
from models.dlq import DLQMessageResponse, DLQStatsResponse

router = APIRouter(prefix="/dlq", tags=["dlq"])


async def get_redis(settings: Settings = Depends(get_settings)) -> redis.Redis:
    """Get Redis client."""
    client = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True,
    )
    try:
        yield client
    finally:
        await client.close()


@router.get("/messages", response_model=list[DLQMessageResponse])
async def list_dlq_messages(
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
    queue: str = "to_secretary",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    error_type: str | None = None,
    user_id: str | None = None,
) -> list[DLQMessageResponse]:
    """List messages in DLQ with optional filters."""
    dlq_stream = f"{queue}:dlq"
    
    entries = await redis_client.xrange(dlq_stream, count=limit * 2)  # Extra for filtering
    
    messages = []
    for msg_id, fields in entries:
        msg = DLQMessageResponse(
            message_id=msg_id,
            original_message_id=fields.get("original_message_id", ""),
            payload=fields.get("payload", ""),
            error_type=fields.get("error_type", "unknown"),
            error_message=fields.get("error_message", ""),
            retry_count=int(fields.get("retry_count", 0)),
            failed_at=datetime.fromisoformat(fields.get("failed_at", datetime.now(UTC).isoformat())),
            user_id=fields.get("user_id"),
        )
        
        # Apply filters
        if error_type and msg.error_type != error_type:
            continue
        if user_id and msg.user_id != user_id:
            continue
            
        messages.append(msg)
        if len(messages) >= limit:
            break
    
    return messages


@router.get("/stats", response_model=DLQStatsResponse)
async def get_dlq_stats(
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
    queue: str = "to_secretary",
) -> DLQStatsResponse:
    """Get DLQ statistics."""
    dlq_stream = f"{queue}:dlq"
    
    total = await redis_client.xlen(dlq_stream)
    
    # Get all messages for stats (limited to 1000)
    entries = await redis_client.xrange(dlq_stream, count=1000)
    
    by_error_type: dict[str, int] = {}
    oldest: datetime | None = None
    newest: datetime | None = None
    
    for _, fields in entries:
        error_type = fields.get("error_type", "unknown")
        by_error_type[error_type] = by_error_type.get(error_type, 0) + 1
        
        failed_at_str = fields.get("failed_at")
        if failed_at_str:
            failed_at = datetime.fromisoformat(failed_at_str)
            if oldest is None or failed_at < oldest:
                oldest = failed_at
            if newest is None or failed_at > newest:
                newest = failed_at
    
    return DLQStatsResponse(
        queue_name=queue,
        total_messages=total,
        by_error_type=by_error_type,
        oldest_message_at=oldest,
        newest_message_at=newest,
    )


@router.post("/messages/{message_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_dlq_message(
    message_id: str,
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
    queue: str = "to_secretary",
) -> dict:
    """Retry a message from DLQ - move back to main queue."""
    dlq_stream = f"{queue}:dlq"
    
    # Get message from DLQ
    entries = await redis_client.xrange(dlq_stream, min=message_id, max=message_id, count=1)
    if not entries:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found in DLQ",
        )
    
    _, fields = entries[0]
    payload = fields.get("payload", "")
    
    # Add back to main queue
    new_id = await redis_client.xadd(queue, {"payload": payload})
    
    # Delete from DLQ
    await redis_client.xdel(dlq_stream, message_id)
    
    return {
        "status": "requeued",
        "original_dlq_message_id": message_id,
        "new_message_id": new_id,
    }


@router.delete("/messages/{message_id}", status_code=status.HTTP_200_OK)
async def delete_dlq_message(
    message_id: str,
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
    queue: str = "to_secretary",
) -> dict:
    """Delete a message from DLQ (after manual review)."""
    dlq_stream = f"{queue}:dlq"
    
    deleted = await redis_client.xdel(dlq_stream, message_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found in DLQ",
        )
    
    return {"status": "deleted", "message_id": message_id}


@router.delete("/messages", status_code=status.HTTP_200_OK)
async def purge_dlq(
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
    queue: str = "to_secretary",
    error_type: str | None = None,
) -> dict:
    """Purge all messages from DLQ (optionally filtered by error_type)."""
    dlq_stream = f"{queue}:dlq"
    
    if error_type:
        # Selective purge
        entries = await redis_client.xrange(dlq_stream)
        deleted_count = 0
        for msg_id, fields in entries:
            if fields.get("error_type") == error_type:
                await redis_client.xdel(dlq_stream, msg_id)
                deleted_count += 1
        return {"status": "purged", "deleted_count": deleted_count, "filter": error_type}
    else:
        # Full purge
        await redis_client.delete(dlq_stream)
        return {"status": "purged", "queue": dlq_stream}
```

### 4.3 Зарегистрировать роутер

В `rest_service/src/main.py` добавить:

```python
from routers import dlq

app.include_router(dlq.router, prefix="/api/v1")
```

### Чек-лист итерации 4

- [ ] Создать `rest_service/src/models/dlq.py`
- [ ] Создать `rest_service/src/routers/dlq.py`
- [ ] Реализовать `GET /api/v1/dlq/messages` - список сообщений
- [ ] Реализовать `GET /api/v1/dlq/stats` - статистика
- [ ] Реализовать `POST /api/v1/dlq/messages/{id}/retry` - повторная отправка
- [ ] Реализовать `DELETE /api/v1/dlq/messages/{id}` - удаление
- [ ] Реализовать `DELETE /api/v1/dlq/messages` - очистка
- [ ] Зарегистрировать роутер в main.py
- [ ] Добавить Redis настройки в config.py если отсутствуют
- [ ] Написать integration тесты для API

---

## Итерация 5: Тестирование

**Цель**: Покрыть тестами новую функциональность

### 5.1 Unit-тесты RedisStreamClient

**Файл**: `assistant_service/tests/unit/test_redis_stream.py`

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from services.redis_stream import RedisStreamClient, MAX_RETRIES, RETRY_DELAYS


@pytest.fixture
def mock_redis():
    return AsyncMock()


@pytest.fixture
def stream_client(mock_redis):
    return RedisStreamClient(
        client=mock_redis,
        stream="test_stream",
        group="test_group",
        consumer="test_consumer",
    )


class TestGetRetryCount:
    def test_returns_zero_when_no_count(self, stream_client):
        assert stream_client.get_retry_count({}) == 0
    
    def test_returns_count_from_string(self, stream_client):
        assert stream_client.get_retry_count({"retry_count": "3"}) == 3
    
    def test_returns_count_from_bytes(self, stream_client):
        assert stream_client.get_retry_count({b"retry_count": b"2"}) == 2


class TestDLQStream:
    def test_dlq_stream_name(self, stream_client):
        assert stream_client.dlq_stream == "test_stream:dlq"


class TestSendToDLQ:
    async def test_sends_message_to_dlq(self, stream_client, mock_redis):
        mock_redis.xadd.return_value = "1234-0"
        
        result = await stream_client.send_to_dlq(
            original_message_id="orig-123",
            payload=b'{"test": "data"}',
            error_info={
                "error_type": "ValueError",
                "error_message": "Test error",
                "user_id": "user-1",
            },
            retry_count=3,
        )
        
        assert result == "1234-0"
        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        assert call_args[0][0] == "test_stream:dlq"


class TestGetRetryDelay:
    def test_returns_correct_delays(self, stream_client):
        assert stream_client.get_retry_delay(0) == RETRY_DELAYS[0]
        assert stream_client.get_retry_delay(1) == RETRY_DELAYS[1]
        assert stream_client.get_retry_delay(2) == RETRY_DELAYS[2]
    
    def test_returns_last_delay_for_high_count(self, stream_client):
        assert stream_client.get_retry_delay(100) == RETRY_DELAYS[-1]
```

### 5.2 Unit-тесты Orchestrator retry логики

**Файл**: `assistant_service/tests/unit/test_orchestrator_retry.py`

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from orchestrator import AssistantOrchestrator


class TestHandleProcessingFailure:
    @pytest.fixture
    def orchestrator(self):
        with patch.object(AssistantOrchestrator, "__init__", lambda x, y: None):
            orch = AssistantOrchestrator(None)
            orch.redis = AsyncMock()
            orch.input_stream = AsyncMock()
            orch.settings = MagicMock()
            orch.settings.INPUT_QUEUE = "test_queue"
            return orch
    
    async def test_increments_retry_count(self, orchestrator):
        orchestrator.redis.incr.return_value = 1
        
        await orchestrator._handle_processing_failure(
            message_id="msg-1",
            raw_payload=b"test",
            error=ValueError("test error"),
            event=None,
        )
        
        orchestrator.redis.incr.assert_called_once()
    
    async def test_sends_to_dlq_after_max_retries(self, orchestrator):
        orchestrator.redis.incr.return_value = MAX_RETRIES
        
        await orchestrator._handle_processing_failure(
            message_id="msg-1",
            raw_payload=b"test",
            error=ValueError("test error"),
            event=None,
        )
        
        orchestrator.input_stream.send_to_dlq.assert_called_once()
        orchestrator.input_stream.ack.assert_called_once()
    
    async def test_does_not_ack_before_max_retries(self, orchestrator):
        orchestrator.redis.incr.return_value = 1  # First retry
        
        await orchestrator._handle_processing_failure(
            message_id="msg-1",
            raw_payload=b"test",
            error=ValueError("test error"),
            event=None,
        )
        
        orchestrator.input_stream.send_to_dlq.assert_not_called()
        orchestrator.input_stream.ack.assert_not_called()
```

### 5.3 Integration-тесты DLQ API

**Файл**: `rest_service/tests/integration/test_dlq_api.py`

```python
import pytest
from httpx import AsyncClient


class TestDLQAPI:
    @pytest.fixture
    async def dlq_message(self, redis_client):
        """Create a test message in DLQ."""
        dlq_stream = "to_secretary:dlq"
        msg_id = await redis_client.xadd(dlq_stream, {
            "payload": '{"content": "test"}',
            "original_message_id": "orig-123",
            "error_type": "TestError",
            "error_message": "Test error message",
            "retry_count": "3",
            "failed_at": "2024-12-16T12:00:00+00:00",
            "user_id": "user-1",
        })
        yield msg_id
        await redis_client.xdel(dlq_stream, msg_id)
    
    async def test_list_dlq_messages(self, client: AsyncClient, dlq_message):
        response = await client.get("/api/v1/dlq/messages")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
    
    async def test_get_dlq_stats(self, client: AsyncClient, dlq_message):
        response = await client.get("/api/v1/dlq/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_messages"] >= 1
    
    async def test_retry_dlq_message(self, client: AsyncClient, dlq_message):
        response = await client.post(f"/api/v1/dlq/messages/{dlq_message}/retry")
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "requeued"
    
    async def test_delete_dlq_message(self, client: AsyncClient, redis_client):
        # Create a message to delete
        dlq_stream = "to_secretary:dlq"
        msg_id = await redis_client.xadd(dlq_stream, {
            "payload": "test",
            "original_message_id": "del-123",
            "error_type": "TestError",
        })
        
        response = await client.delete(f"/api/v1/dlq/messages/{msg_id}")
        assert response.status_code == 200
```

### Чек-лист итерации 5

- [ ] Unit-тесты `RedisStreamClient` - все новые методы
- [ ] Unit-тесты `AssistantOrchestrator` - retry логика
- [ ] Unit-тесты `AssistantOrchestrator` - DLQ отправка
- [ ] Integration-тесты DLQ REST API
- [ ] Тест E2E: сообщение → ошибка → retry → DLQ
- [ ] Запустить `make test-unit SERVICE=assistant_service`
- [ ] Запустить `make test-integration SERVICE=rest_service`

---

## Итерация 6: Документация и мониторинг

**Цель**: Обновить документацию и настроить алерты

### 6.1 Обновить AGENTS.md

Добавить раздел про DLQ механизм:

```markdown
## Dead Letter Queue (DLQ)

### Механизм обработки ошибок

При ошибке обработки сообщения в `assistant_service`:
1. Счетчик retry увеличивается (хранится в Redis ключе `msg_retry:{message_id}`)
2. Если retry_count < MAX_RETRIES (3):
   - Сообщение НЕ ACK-ается
   - Остается в pending для повторной обработки через xautoclaim (60s idle)
3. Если retry_count >= MAX_RETRIES:
   - Сообщение отправляется в DLQ stream `{queue}:dlq`
   - Оригинальное сообщение ACK-ается

### DLQ REST API

- `GET /api/v1/dlq/messages` - список сообщений в DLQ
- `GET /api/v1/dlq/stats` - статистика DLQ
- `POST /api/v1/dlq/messages/{id}/retry` - повторная отправка
- `DELETE /api/v1/dlq/messages/{id}` - удаление после разбора

### Prometheus метрики

- `messages_dlq_total{error_type, queue}` - счетчик сообщений в DLQ
- `message_processing_retries_total{queue}` - количество retry
- `dlq_size{queue}` - текущий размер DLQ
```

### 6.2 Настроить Grafana алерты

Создать alert rule в `monitoring/grafana/provisioning/alerting/`:

```yaml
# dlq_alerts.yaml
groups:
  - name: DLQ Alerts
    rules:
      - alert: DLQSizeHigh
        expr: dlq_size > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "DLQ size is high"
          description: "DLQ {{ $labels.queue }} has {{ $value }} messages"
      
      - alert: DLQGrowthRapid
        expr: increase(messages_dlq_total[5m]) > 10
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Rapid DLQ growth detected"
          description: "{{ $value }} messages sent to DLQ in last 5 minutes"
```

### 6.3 Создать Grafana dashboard panel

Добавить панель в существующий dashboard для:
- График `messages_dlq_total` rate
- Текущее значение `dlq_size`
- Top error types pie chart
- Retry rate over time

### Чек-лист итерации 6

- [ ] Обновить AGENTS.md с описанием DLQ
- [ ] Создать документ `docs/dlq_operations_guide.md` с инструкциями по эксплуатации
- [ ] Настроить Grafana alert для DLQ size
- [ ] Настроить Grafana alert для DLQ growth rate
- [ ] Добавить DLQ панели в Grafana dashboard
- [ ] Протестировать алерты
- [ ] Обновить BACKLOG.md - отметить задачу выполненной

---

## Порядок выполнения

1. **Итерация 1** (1-2 часа): RedisStreamClient - базовая функциональность DLQ
2. **Итерация 2** (2-3 часа): Orchestrator - изменение логики ACK и retry
3. **Итерация 3** (1 час): Метрики Prometheus
4. **Итерация 4** (2-3 часа): REST API для DLQ
5. **Итерация 5** (2-3 часа): Тестирование
6. **Итерация 6** (1-2 часа): Документация и мониторинг

**Общая оценка**: 9-14 часов

## Риски и митигации

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Сообщения застрянут в pending навсегда | Средняя | xautoclaim с idle_reclaim_ms=60000 решает |
| Потеря retry_count при рестарте сервиса | Низкая | Хранение в Redis с TTL |
| DLQ переполнится | Низкая | Алерт + REST API для очистки |
| Дублирование сообщений при retry | Средняя | Идемпотентная обработка на стороне потребителя |

## Критерии приемки

- [ ] Сообщения не теряются при ошибках обработки
- [ ] После MAX_RETRIES сообщение попадает в DLQ
- [ ] Можно просмотреть и управлять DLQ через REST API
- [ ] Метрики доступны в Prometheus/Grafana
- [ ] Алерты настроены и работают
- [ ] Unit и integration тесты проходят
- [ ] Документация обновлена
