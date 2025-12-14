"""Correlation ID middleware for request tracing."""

import uuid

from fastapi import Request
from shared_models import clear_context, set_correlation_id, set_user_id
from starlette.middleware.base import BaseHTTPMiddleware

CORRELATION_ID_HEADER = "X-Correlation-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that extracts or generates correlation_id for each request.

    The correlation_id is:
    1. Taken from X-Correlation-ID header if present
    2. Generated as UUID if not present
    3. Added to response headers
    4. Set in context for logging
    """

    async def dispatch(self, request: Request, call_next):
        # Get or generate correlation_id
        correlation_id = request.headers.get(CORRELATION_ID_HEADER)
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Set in context for logging
        set_correlation_id(correlation_id)

        # Try to extract user_id from path or query params
        user_id = None
        if "user_id" in request.path_params:
            try:
                user_id = int(request.path_params["user_id"])
            except (ValueError, TypeError):
                pass
        if user_id is None and "user_id" in request.query_params:
            try:
                user_id = int(request.query_params["user_id"])
            except (ValueError, TypeError):
                pass
        if user_id:
            set_user_id(user_id)

        try:
            response = await call_next(request)
            # Add correlation_id to response headers
            response.headers[CORRELATION_ID_HEADER] = correlation_id
            return response
        finally:
            # Clear context after request
            clear_context()
