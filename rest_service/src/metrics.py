"""Prometheus metrics for rest_service."""

import re
import time

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# HTTP metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Patterns to normalize endpoints
UUID_PATTERN = re.compile(r"/[0-9a-f-]{36}")
INT_PATTERN = re.compile(r"/\d+")


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting HTTP request metrics."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start_time

        # Normalize endpoint
        endpoint = request.url.path
        endpoint = UUID_PATTERN.sub("/{id}", endpoint)
        endpoint = INT_PATTERN.sub("/{id}", endpoint)

        if endpoint not in ("/metrics", "/health"):
            http_requests_total.labels(
                method=request.method,
                endpoint=endpoint,
                status=response.status_code,
            ).inc()
            http_request_duration_seconds.labels(
                method=request.method,
                endpoint=endpoint,
            ).observe(duration)

        return response


def get_metrics() -> bytes:
    """Return metrics in Prometheus format."""
    return generate_latest()


def get_content_type() -> str:
    """Return Prometheus content type."""
    return CONTENT_TYPE_LATEST
