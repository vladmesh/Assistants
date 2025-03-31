import logging
import sys
from typing import Any, Dict

import structlog


def configure_logger(environment: str = "development") -> None:
    """
    Configure structured logger based on environment

    Args:
        environment: Current environment (development/production)
    """
    # Set up standard logging
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)

    # Configure structlog
    structlog.configure(
        processors=[
            # Add timestamp in a more readable format
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S.%f%z"),
            # Add log level
            structlog.processors.add_log_level,
            # Add logger name
            structlog.contextvars.merge_contextvars,
            # Add file and line number
            structlog.processors.CallsiteParameterAdder(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            # Use better console output in development
            (
                structlog.dev.ConsoleRenderer(colors=True, sort_keys=True)
                if environment == "development"
                else structlog.processors.JSONRenderer()
            ),
        ],
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a configured logger instance

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    return structlog.get_logger(name)


# Configure logger on import
configure_logger()

# Default logger instance
logger = get_logger("calendar_service")
