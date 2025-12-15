import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from shared_models import LogEventType, configure_logging, get_logger

import metrics
from config import settings
from scheduler import start_scheduler

# Configure logging
configure_logging(
    service_name="cron_service",
    log_level=settings.LOG_LEVEL,
    json_format=settings.LOG_JSON_FORMAT,
)
logger = get_logger(__name__)


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for Prometheus metrics and health check."""

    def do_GET(self):
        if self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", metrics.get_content_type())
            self.end_headers()
            self.wfile.write(metrics.get_metrics())
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress default logging


def start_metrics_server(port: int = 8080):
    """Start HTTP server for Prometheus metrics."""
    server = HTTPServer(("0.0.0.0", port), MetricsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Metrics server started on port {port}")
    return server


def main():
    logger.info("Starting Cron Service", event_type=LogEventType.STARTUP)

    # Start metrics server
    metrics_port = getattr(settings, "METRICS_PORT", 8080)
    start_metrics_server(metrics_port)

    # Start scheduler (blocks)
    start_scheduler()


if __name__ == "__main__":
    main()
