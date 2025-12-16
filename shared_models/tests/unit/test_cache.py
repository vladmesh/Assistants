"""Tests for RedisCache."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

from shared_models.cache import CachedServiceClient, RedisCache


class TestModel(BaseModel):
    """Test Pydantic model for cache tests."""

    id: int
    name: str


class MockRedisClient:
    """Mock async Redis client for testing."""

    def __init__(self):
        self._store: dict[str, str] = {}
        self._ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value
        self._ttls[key] = ttl

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                self._ttls.pop(key, None)
                deleted += 1
        return deleted

    async def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    async def ttl(self, key: str) -> int:
        if key not in self._store:
            return -2
        return self._ttls.get(key, -1)

    async def publish(self, channel: str, message: str) -> int:
        return 1

    def pubsub(self):
        return AsyncMock()

    async def scan_iter(self, match: str):
        """Async generator for scanning keys."""
        import fnmatch

        for key in list(self._store.keys()):
            if fnmatch.fnmatch(key, match):
                yield key


@pytest.fixture
def mock_redis():
    return MockRedisClient()


@pytest.fixture
def cache(mock_redis):
    return RedisCache(mock_redis, prefix="test")


class TestRedisCache:
    """Tests for RedisCache."""

    @pytest.mark.asyncio
    async def test_set_and_get_pydantic_model(self, cache):
        """Test setting and getting a Pydantic model."""
        model = TestModel(id=1, name="test")

        result = await cache.set("model:1", model, ttl=300)
        assert result is True

        retrieved = await cache.get("model:1", TestModel)
        assert retrieved is not None
        assert retrieved.id == 1
        assert retrieved.name == "test"

    @pytest.mark.asyncio
    async def test_set_and_get_dict(self, cache):
        """Test setting and getting a dict."""
        data = {"key": "value", "number": 42}

        result = await cache.set("dict:1", data, ttl=300)
        assert result is True

        retrieved = await cache.get_raw("dict:1")
        assert retrieved == data

    @pytest.mark.asyncio
    async def test_set_and_get_list(self, cache):
        """Test setting and getting a list."""
        data = [{"id": 1}, {"id": 2}]

        result = await cache.set("list:1", data, ttl=300)
        assert result is True

        retrieved = await cache.get_raw("list:1")
        assert retrieved == data

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self, cache):
        """Test getting a nonexistent key returns None."""
        result = await cache.get("nonexistent", TestModel)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_raw_nonexistent_key(self, cache):
        """Test get_raw for nonexistent key returns None."""
        result = await cache.get_raw("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, cache):
        """Test deleting a cached value."""
        await cache.set("to_delete", {"data": "value"}, ttl=300)

        # Verify it exists
        assert await cache.get_raw("to_delete") is not None

        # Delete it
        result = await cache.delete("to_delete")
        assert result is True

        # Verify it's gone
        assert await cache.get_raw("to_delete") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, cache):
        """Test deleting a nonexistent key."""
        result = await cache.delete("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_exists(self, cache):
        """Test checking if key exists."""
        await cache.set("exists_test", {"data": "value"}, ttl=300)

        assert await cache.exists("exists_test") is True
        assert await cache.exists("nonexistent") is False

    @pytest.mark.asyncio
    async def test_get_ttl(self, cache, mock_redis):
        """Test getting TTL for a key."""
        await cache.set("ttl_test", {"data": "value"}, ttl=300)

        ttl = await cache.get_ttl("ttl_test")
        assert ttl == 300

    @pytest.mark.asyncio
    async def test_get_ttl_nonexistent(self, cache):
        """Test getting TTL for nonexistent key."""
        ttl = await cache.get_ttl("nonexistent")
        assert ttl == -2

    @pytest.mark.asyncio
    async def test_invalidate_pattern(self, cache, mock_redis):
        """Test invalidating keys by pattern."""
        # Set multiple keys
        await cache.set("user:1", {"id": 1}, ttl=300)
        await cache.set("user:2", {"id": 2}, ttl=300)
        await cache.set("other:1", {"id": 1}, ttl=300)

        # Invalidate user:* pattern
        deleted = await cache.invalidate("user:*")

        assert deleted == 2
        assert await cache.get_raw("user:1") is None
        assert await cache.get_raw("user:2") is None
        assert await cache.get_raw("other:1") is not None

    @pytest.mark.asyncio
    async def test_invalidate_no_matches(self, cache):
        """Test invalidating with no matching keys."""
        await cache.set("other:1", {"id": 1}, ttl=300)

        deleted = await cache.invalidate("nomatch:*")
        assert deleted == 0

    @pytest.mark.asyncio
    async def test_key_prefix(self, cache, mock_redis):
        """Test that keys are prefixed correctly."""
        await cache.set("mykey", {"data": "value"}, ttl=300)

        # Check the actual key in mock store
        assert "test:mykey" in mock_redis._store

    @pytest.mark.asyncio
    async def test_ttl_as_timedelta(self, cache, mock_redis):
        """Test setting TTL as timedelta."""
        await cache.set("timedelta_test", {"data": "value"}, ttl=timedelta(minutes=5))

        assert mock_redis._ttls.get("test:timedelta_test") == 300

    @pytest.mark.asyncio
    async def test_set_error_handling(self, cache):
        """Test error handling during set."""
        with patch.object(cache.redis, "setex", side_effect=Exception("Redis error")):
            result = await cache.set("error_test", {"data": "value"}, ttl=300)
            assert result is False

    @pytest.mark.asyncio
    async def test_get_error_handling(self, cache):
        """Test error handling during get."""
        with patch.object(cache.redis, "get", side_effect=Exception("Redis error")):
            result = await cache.get("error_test", TestModel)
            assert result is None

    @pytest.mark.asyncio
    async def test_get_raw_error_handling(self, cache):
        """Test error handling during get_raw."""
        with patch.object(cache.redis, "get", side_effect=Exception("Redis error")):
            result = await cache.get_raw("error_test")
            assert result is None


class TestCachedServiceClient:
    """Tests for CachedServiceClient mixin."""

    @pytest.mark.asyncio
    async def test_cache_not_set(self):
        """Test cache operations when cache is not set."""

        class TestClient(CachedServiceClient):
            pass

        client = TestClient()

        # All operations should return None/False when cache not set
        assert await client.cache_get("key", TestModel) is None
        assert await client.cache_get_raw("key") is None
        assert await client.cache_set("key", {"data": "value"}) is False
        assert await client.cache_delete("key") is False
        assert await client.cache_invalidate("pattern:*") == 0

    @pytest.mark.asyncio
    async def test_cache_operations(self, mock_redis):
        """Test cache operations when cache is set."""

        class TestClient(CachedServiceClient):
            pass

        client = TestClient()
        cache = RedisCache(mock_redis, prefix="client")
        client.set_cache(cache, default_ttl=600)

        model = TestModel(id=1, name="test")

        # Test set
        result = await client.cache_set("model:1", model)
        assert result is True

        # Test get
        retrieved = await client.cache_get("model:1", TestModel)
        assert retrieved is not None
        assert retrieved.id == 1

        # Test get_raw
        await client.cache_set("raw:1", {"key": "value"})
        raw = await client.cache_get_raw("raw:1")
        assert raw == {"key": "value"}

        # Test delete
        deleted = await client.cache_delete("raw:1")
        assert deleted is True

        # Test invalidate
        await client.cache_set("inv:1", {"data": 1})
        await client.cache_set("inv:2", {"data": 2})
        count = await client.cache_invalidate("inv:*")
        assert count == 2

    @pytest.mark.asyncio
    async def test_default_ttl(self, mock_redis):
        """Test that default TTL is used when not specified."""

        class TestClient(CachedServiceClient):
            pass

        client = TestClient()
        cache = RedisCache(mock_redis, prefix="client")
        client.set_cache(cache, default_ttl=600)

        await client.cache_set("test", {"data": "value"})

        # Check TTL in mock store
        assert mock_redis._ttls.get("client:test") == 600

    @pytest.mark.asyncio
    async def test_custom_ttl(self, mock_redis):
        """Test that custom TTL overrides default."""

        class TestClient(CachedServiceClient):
            pass

        client = TestClient()
        cache = RedisCache(mock_redis, prefix="client")
        client.set_cache(cache, default_ttl=600)

        await client.cache_set("test", {"data": "value"}, ttl=120)

        # Check TTL in mock store
        assert mock_redis._ttls.get("client:test") == 120


class TestMetrics:
    """Tests for cache metrics."""

    @pytest.mark.asyncio
    async def test_cache_hit_metric(self, cache, mock_redis):
        """Test cache hit metric is incremented."""
        await cache.set("hit_test", {"data": "value"}, ttl=300)

        from shared_models.cache import CACHE_HITS_TOTAL

        # Get initial value
        initial = CACHE_HITS_TOTAL.labels(
            cache_name="test", key_pattern="hit_test"
        )._value.get()

        # Access cached value
        await cache.get_raw("hit_test")

        # Check metric incremented
        final = CACHE_HITS_TOTAL.labels(
            cache_name="test", key_pattern="hit_test"
        )._value.get()
        assert final > initial

    @pytest.mark.asyncio
    async def test_cache_miss_metric(self, cache):
        """Test cache miss metric is incremented."""
        from shared_models.cache import CACHE_MISSES_TOTAL

        # Get initial value
        initial = CACHE_MISSES_TOTAL.labels(
            cache_name="test", key_pattern="miss_test"
        )._value.get()

        # Access nonexistent value
        await cache.get_raw("miss_test")

        # Check metric incremented
        final = CACHE_MISSES_TOTAL.labels(
            cache_name="test", key_pattern="miss_test"
        )._value.get()
        assert final > initial


class TestPatternExtraction:
    """Tests for key pattern extraction for metrics."""

    def test_extract_numeric_id(self, cache):
        """Test numeric ID is replaced in pattern."""
        pattern = cache._extract_pattern("user:123")
        assert pattern == "user:*"

    def test_extract_uuid(self, cache):
        """Test UUID is replaced in pattern."""
        pattern = cache._extract_pattern(
            "assistant:550e8400-e29b-41d4-a716-446655440000"
        )
        assert pattern == "assistant:*"

    def test_extract_multiple_ids(self, cache):
        """Test multiple IDs are replaced."""
        pattern = cache._extract_pattern("user:123:message:456")
        assert pattern == "user:*:message:*"

    def test_extract_no_id(self, cache):
        """Test pattern without ID stays unchanged."""
        pattern = cache._extract_pattern("global_settings")
        assert pattern == "global_settings"
