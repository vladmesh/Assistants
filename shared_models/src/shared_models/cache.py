"""Redis cache wrapper with TTL and invalidation support.

Provides:
- Type-safe get/set with Pydantic models
- TTL support
- Pattern-based invalidation
- Pub/Sub for cache invalidation events
- Prometheus metrics
"""

import json
from datetime import timedelta
from typing import TypeVar

from prometheus_client import Counter, Histogram
from pydantic import BaseModel

from shared_models.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

# === Prometheus Metrics ===

CACHE_HITS_TOTAL = Counter(
    "redis_cache_hits_total",
    "Total cache hits",
    ["cache_name", "key_pattern"],
)

CACHE_MISSES_TOTAL = Counter(
    "redis_cache_misses_total",
    "Total cache misses",
    ["cache_name", "key_pattern"],
)

CACHE_OPERATIONS_DURATION = Histogram(
    "redis_cache_operations_duration_seconds",
    "Cache operation duration in seconds",
    ["cache_name", "operation"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
)


class RedisCache:
    """Redis cache with typed get/set and Pub/Sub invalidation.

    Usage:
        import redis.asyncio as redis
        from shared_models.cache import RedisCache

        client = redis.Redis(host="localhost", port=6379, db=0)
        cache = RedisCache(client, prefix="api_cache")

        # Set with Pydantic model
        await cache.set("user:1", user_model, ttl=300)

        # Get with type
        user = await cache.get("user:1", UserModel)

        # Invalidate pattern
        await cache.invalidate("user:*")
    """

    INVALIDATION_CHANNEL = "cache:invalidation"

    def __init__(self, redis_client, prefix: str = "cache"):
        """Initialize cache wrapper.

        Args:
            redis_client: Async redis client (redis.asyncio.Redis)
            prefix: Key prefix for all cache entries
        """
        self.redis = redis_client
        self.prefix = prefix
        self._pubsub = None

    def _key(self, key: str) -> str:
        """Build full cache key with prefix."""
        return f"{self.prefix}:{key}"

    def _extract_pattern(self, key: str) -> str:
        """Extract pattern from key for metrics (remove specific IDs)."""
        import re

        # UUID pattern must be applied first (before numeric replacement)
        pattern = re.sub(
            r":[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            ":*",
            key,
            flags=re.IGNORECASE,
        )
        # Then replace numeric IDs
        pattern = re.sub(r":\d+", ":*", pattern)
        return pattern

    async def get(self, key: str, model_class: type[T]) -> T | None:
        """Get cached value and deserialize to Pydantic model.

        Args:
            key: Cache key (without prefix)
            model_class: Pydantic model class for deserialization

        Returns:
            Deserialized model instance or None if not found/error
        """
        import time

        full_key = self._key(key)
        key_pattern = self._extract_pattern(key)
        start_time = time.perf_counter()

        try:
            data = await self.redis.get(full_key)
            duration = time.perf_counter() - start_time

            CACHE_OPERATIONS_DURATION.labels(
                cache_name=self.prefix,
                operation="get",
            ).observe(duration)

            if data is None:
                CACHE_MISSES_TOTAL.labels(
                    cache_name=self.prefix,
                    key_pattern=key_pattern,
                ).inc()
                return None

            CACHE_HITS_TOTAL.labels(
                cache_name=self.prefix,
                key_pattern=key_pattern,
            ).inc()

            return model_class.model_validate_json(data)

        except Exception as e:
            logger.warning(
                "Cache get failed",
                key=key,
                error=str(e),
                cache_name=self.prefix,
            )
            CACHE_MISSES_TOTAL.labels(
                cache_name=self.prefix,
                key_pattern=key_pattern,
            ).inc()
            return None

    async def get_raw(self, key: str) -> dict | list | None:
        """Get cached value as raw dict/list.

        Args:
            key: Cache key (without prefix)

        Returns:
            Parsed JSON data or None if not found/error
        """
        import time

        full_key = self._key(key)
        key_pattern = self._extract_pattern(key)
        start_time = time.perf_counter()

        try:
            data = await self.redis.get(full_key)
            duration = time.perf_counter() - start_time

            CACHE_OPERATIONS_DURATION.labels(
                cache_name=self.prefix,
                operation="get_raw",
            ).observe(duration)

            if data is None:
                CACHE_MISSES_TOTAL.labels(
                    cache_name=self.prefix,
                    key_pattern=key_pattern,
                ).inc()
                return None

            CACHE_HITS_TOTAL.labels(
                cache_name=self.prefix,
                key_pattern=key_pattern,
            ).inc()

            return json.loads(data)

        except Exception as e:
            logger.warning(
                "Cache get_raw failed",
                key=key,
                error=str(e),
                cache_name=self.prefix,
            )
            CACHE_MISSES_TOTAL.labels(
                cache_name=self.prefix,
                key_pattern=key_pattern,
            ).inc()
            return None

    async def set(
        self,
        key: str,
        value: BaseModel | dict | list,
        ttl: timedelta | int = 300,
    ) -> bool:
        """Set cached value with TTL.

        Args:
            key: Cache key (without prefix)
            value: Value to cache (Pydantic model, dict, or list)
            ttl: Time to live in seconds or timedelta (default: 300s)

        Returns:
            True if successful, False otherwise
        """
        import time

        full_key = self._key(key)
        start_time = time.perf_counter()

        try:
            if isinstance(value, BaseModel):
                data = value.model_dump_json()
            else:
                data = json.dumps(value)

            ttl_seconds = ttl.total_seconds() if isinstance(ttl, timedelta) else ttl
            await self.redis.setex(full_key, int(ttl_seconds), data)

            duration = time.perf_counter() - start_time
            CACHE_OPERATIONS_DURATION.labels(
                cache_name=self.prefix,
                operation="set",
            ).observe(duration)

            logger.debug(
                "Cache set",
                key=key,
                ttl_seconds=int(ttl_seconds),
                cache_name=self.prefix,
            )
            return True

        except Exception as e:
            logger.warning(
                "Cache set failed",
                key=key,
                error=str(e),
                cache_name=self.prefix,
            )
            return False

    async def delete(self, key: str) -> bool:
        """Delete cached value.

        Args:
            key: Cache key (without prefix)

        Returns:
            True if deleted, False otherwise
        """
        import time

        full_key = self._key(key)
        start_time = time.perf_counter()

        try:
            deleted = await self.redis.delete(full_key)

            duration = time.perf_counter() - start_time
            CACHE_OPERATIONS_DURATION.labels(
                cache_name=self.prefix,
                operation="delete",
            ).observe(duration)

            logger.debug(
                "Cache delete",
                key=key,
                deleted=bool(deleted),
                cache_name=self.prefix,
            )
            return bool(deleted)

        except Exception as e:
            logger.warning(
                "Cache delete failed",
                key=key,
                error=str(e),
                cache_name=self.prefix,
            )
            return False

    async def invalidate(self, pattern: str) -> int:
        """Invalidate all keys matching pattern and notify subscribers.

        Args:
            pattern: Glob pattern to match (e.g., "user:*", "assistant:*")

        Returns:
            Number of keys deleted
        """
        import time

        full_pattern = self._key(pattern)
        start_time = time.perf_counter()

        try:
            keys = []
            async for key in self.redis.scan_iter(match=full_pattern):
                keys.append(key)

            deleted_count = 0
            if keys:
                deleted_count = await self.redis.delete(*keys)
                # Publish invalidation event
                await self.redis.publish(
                    self.INVALIDATION_CHANNEL,
                    json.dumps(
                        {
                            "pattern": pattern,
                            "keys_deleted": deleted_count,
                            "cache_name": self.prefix,
                        }
                    ),
                )

            duration = time.perf_counter() - start_time
            CACHE_OPERATIONS_DURATION.labels(
                cache_name=self.prefix,
                operation="invalidate",
            ).observe(duration)

            logger.info(
                "Cache invalidated",
                pattern=pattern,
                keys_deleted=deleted_count,
                cache_name=self.prefix,
            )
            return deleted_count

        except Exception as e:
            logger.warning(
                "Cache invalidate failed",
                pattern=pattern,
                error=str(e),
                cache_name=self.prefix,
            )
            return 0

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key (without prefix)

        Returns:
            True if exists, False otherwise
        """
        full_key = self._key(key)
        try:
            return bool(await self.redis.exists(full_key))
        except Exception as e:
            logger.warning(
                "Cache exists check failed",
                key=key,
                error=str(e),
                cache_name=self.prefix,
            )
            return False

    async def get_ttl(self, key: str) -> int | None:
        """Get remaining TTL for a key.

        Args:
            key: Cache key (without prefix)

        Returns:
            TTL in seconds, -1 if no TTL, -2 if key doesn't exist, None on error
        """
        full_key = self._key(key)
        try:
            ttl = await self.redis.ttl(full_key)
            return ttl
        except Exception as e:
            logger.warning(
                "Cache TTL check failed",
                key=key,
                error=str(e),
                cache_name=self.prefix,
            )
            return None

    async def subscribe_invalidation(self, callback) -> None:
        """Subscribe to cache invalidation events.

        Args:
            callback: Async callback function that receives invalidation data dict
                     Example: async def on_invalidate(data: dict): ...
        """
        self._pubsub = self.redis.pubsub()
        await self._pubsub.subscribe(self.INVALIDATION_CHANNEL)

        logger.info(
            "Subscribed to cache invalidation channel",
            channel=self.INVALIDATION_CHANNEL,
            cache_name=self.prefix,
        )

        async for message in self._pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await callback(data)
                except Exception as e:
                    logger.warning(
                        "Invalidation callback failed",
                        error=str(e),
                        cache_name=self.prefix,
                    )

    async def unsubscribe_invalidation(self) -> None:
        """Unsubscribe from cache invalidation events."""
        if self._pubsub:
            await self._pubsub.unsubscribe(self.INVALIDATION_CHANNEL)
            await self._pubsub.close()
            self._pubsub = None
            logger.info(
                "Unsubscribed from cache invalidation channel",
                cache_name=self.prefix,
            )


class CachedServiceClient:
    """Mixin for service clients to add caching capabilities.

    Usage:
        class MyClient(CachedServiceClient, BaseServiceClient):
            async def get_user(self, user_id: int) -> UserModel | None:
                cache_key = f"user:{user_id}"

                # Try cache first
                cached = await self.cache_get(cache_key, UserModel)
                if cached:
                    return cached

                # Fetch from API
                result = await self.request("GET", f"/api/users/{user_id}")
                if result:
                    user = UserModel(**result)
                    await self.cache_set(cache_key, user, ttl=300)
                    return user
                return None
    """

    _cache: RedisCache | None = None
    _default_ttl: int = 300

    def set_cache(self, cache: RedisCache, default_ttl: int = 300) -> None:
        """Set cache instance for this client.

        Args:
            cache: RedisCache instance
            default_ttl: Default TTL in seconds (default: 300)
        """
        self._cache = cache
        self._default_ttl = default_ttl

    async def cache_get(self, key: str, model_class: type[T]) -> T | None:
        """Get value from cache.

        Args:
            key: Cache key
            model_class: Pydantic model class

        Returns:
            Cached value or None
        """
        if self._cache is None:
            return None
        return await self._cache.get(key, model_class)

    async def cache_get_raw(self, key: str) -> dict | list | None:
        """Get raw value from cache.

        Args:
            key: Cache key

        Returns:
            Cached dict/list or None
        """
        if self._cache is None:
            return None
        return await self._cache.get_raw(key)

    async def cache_set(
        self,
        key: str,
        value: BaseModel | dict | list,
        ttl: int | None = None,
    ) -> bool:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (uses default if None)

        Returns:
            True if successful
        """
        if self._cache is None:
            return False
        return await self._cache.set(key, value, ttl or self._default_ttl)

    async def cache_delete(self, key: str) -> bool:
        """Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted
        """
        if self._cache is None:
            return False
        return await self._cache.delete(key)

    async def cache_invalidate(self, pattern: str) -> int:
        """Invalidate cache by pattern.

        Args:
            pattern: Glob pattern

        Returns:
            Number of keys deleted
        """
        if self._cache is None:
            return 0
        return await self._cache.invalidate(pattern)
