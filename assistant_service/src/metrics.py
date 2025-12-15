"""Prometheus metrics for assistant_service."""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
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
