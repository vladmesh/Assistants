"""Middleware for cache invalidation on data changes."""

from fastapi import Request
from shared_models import RedisCache, get_logger
from starlette.middleware.base import BaseHTTPMiddleware

logger = get_logger(__name__)


class CacheInvalidationMiddleware(BaseHTTPMiddleware):
    """Invalidate cache on mutating operations.

    This middleware monitors successful mutating HTTP operations
    (POST, PUT, PATCH, DELETE) and invalidates relevant cache entries
    based on the request path.

    Uses app.state.cache for lazy cache access (cache initialized in lifespan).
    """

    # Mapping of (HTTP method, path prefix) -> cache pattern to invalidate
    INVALIDATION_RULES: dict[tuple[str, str], str] = {
        # Assistants
        ("POST", "/api/assistants"): "assistant:*",
        ("PUT", "/api/assistants"): "assistant:*",
        ("PATCH", "/api/assistants"): "assistant:*",
        ("DELETE", "/api/assistants"): "assistant:*",
        # Tools
        ("POST", "/api/tools"): "tools:*",
        ("PUT", "/api/tools"): "tools:*",
        ("PATCH", "/api/tools"): "tools:*",
        ("DELETE", "/api/tools"): "tools:*",
        # Assistant Tools (linking)
        ("POST", "/api/assistant-tools"): "assistant:*",
        ("DELETE", "/api/assistant-tools"): "assistant:*",
        # Global Settings
        ("PUT", "/api/global-settings"): "settings:*",
        ("PATCH", "/api/global-settings"): "settings:*",
        # Users
        ("POST", "/api/users"): "user:*",
        ("PUT", "/api/users"): "user:*",
        ("PATCH", "/api/users"): "user:*",
        ("DELETE", "/api/users"): "user:*",
        # User Secretaries (assignments)
        ("POST", "/api/user-secretaries"): "secretary:*",
        ("PUT", "/api/user-secretaries"): "secretary:*",
        ("PATCH", "/api/user-secretaries"): "secretary:*",
        ("DELETE", "/api/user-secretaries"): "secretary:*",
    }

    async def dispatch(self, request: Request, call_next):
        """Process request and invalidate cache on successful mutations."""
        response = await call_next(request)

        # Only invalidate on successful mutating operations (2xx status)
        if response.status_code < 300:
            await self._maybe_invalidate(request, request.method, request.url.path)

        return response

    async def _maybe_invalidate(self, request: Request, method: str, path: str) -> None:
        """Check if cache should be invalidated based on request.

        Args:
            request: FastAPI request (to access app.state)
            method: HTTP method (GET, POST, etc.)
            path: Request path
        """
        # Get cache from app.state (lazy access)
        cache: RedisCache | None = getattr(request.app.state, "cache", None)
        if cache is None:
            return

        for (rule_method, rule_prefix), pattern in self.INVALIDATION_RULES.items():
            if method == rule_method and path.startswith(rule_prefix):
                logger.debug(
                    "Invalidating cache",
                    method=method,
                    path=path,
                    pattern=pattern,
                )
                await cache.invalidate(pattern)
                break
