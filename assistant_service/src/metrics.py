"""Prometheus metrics for assistant_service."""

import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.redis_stream import RedisStreamClient

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# LLM metrics
llm_requests_total = Counter(
    "llm_requests_total",
    "Total LLM API requests",
    ["model", "status"],
)

llm_request_duration_seconds = Histogram(
    "llm_request_duration_seconds",
    "LLM request duration",
    ["model"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0],
)

llm_tokens_total = Counter(
    "llm_tokens_total",
    "Total tokens used",
    ["model", "type"],
)

# Tool metrics
tool_calls_total = Counter(
    "tool_calls_total",
    "Total tool calls",
    ["tool_name", "status"],
)

# Message processing metrics
messages_processed_total = Counter(
    "messages_processed_total",
    "Total messages processed",
    ["source", "status"],
)

message_processing_duration_seconds = Histogram(
    "message_processing_duration_seconds",
    "Message processing duration",
    ["source"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0],
)

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
    ["queue", "outcome"],
    buckets=[0, 1, 2, 3, 4, 5],
)


def get_metrics() -> bytes:
    """Return metrics in Prometheus format."""
    return generate_latest()


def get_content_type() -> str:
    """Return Prometheus content type."""
    return CONTENT_TYPE_LATEST


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for /metrics and /health endpoints."""

    def do_GET(self):
        if self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", get_content_type())
            self.end_headers()
            self.wfile.write(get_metrics())
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress logging


def start_metrics_server(port: int = 8080) -> HTTPServer:
    """Start HTTP server for Prometheus metrics."""
    server = HTTPServer(("0.0.0.0", port), MetricsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


async def update_dlq_metrics(
    input_stream: "RedisStreamClient",
    interval: int = 60,
) -> None:
    """Periodically update DLQ size gauge.

    Args:
        input_stream: Redis stream client with DLQ methods.
        interval: Update interval in seconds (default: 60).
    """
    from shared_models import get_logger

    logger = get_logger(__name__)

    while True:
        try:
            size = await input_stream.get_dlq_length()
            dlq_size.labels(queue=input_stream.stream).set(size)
        except Exception as e:
            logger.warning("Failed to update DLQ metrics", error=str(e))
        await asyncio.sleep(interval)
