"""
Legacy logger module for backward compatibility.
Use shared_models.logging instead for new code.
"""

from shared_models import configure_logging, get_logger

from config.settings import settings

# Auto-configure if not already done
configure_logging(
    service_name="assistant_service",
    log_level=settings.LOG_LEVEL,
    json_format=settings.LOG_JSON_FORMAT,
)

# Default logger instance
logger = get_logger("assistant")

__all__ = ["configure_logging", "get_logger", "logger"]
