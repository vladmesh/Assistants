"""Prometheus metrics for telegram_bot_service."""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

# Telegram metrics
telegram_updates_total = Counter(
    "telegram_updates_total",
    "Total Telegram updates received",
    ["update_type"],
)

telegram_messages_sent_total = Counter(
    "telegram_messages_sent_total",
    "Total messages sent to Telegram",
    ["status"],
)

message_processing_duration_seconds = Histogram(
    "message_processing_duration_seconds",
    "Message processing duration",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
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
