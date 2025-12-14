"""
Legacy logger module for backward compatibility.
Use shared_models.logging instead for new code.
"""

from shared_models import configure_logging, get_logger

from config.settings import Settings

settings = Settings()

# Auto-configure if not already done
configure_logging(
    service_name="google_calendar_service",
    log_level=settings.LOG_LEVEL,
    json_format=settings.LOG_JSON_FORMAT,
)

# Default logger instance
logger = get_logger("calendar_service")

__all__ = ["configure_logging", "get_logger", "logger"]
