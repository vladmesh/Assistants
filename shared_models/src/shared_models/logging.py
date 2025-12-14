"""
Unified logging configuration for all Smart Assistant services.

Usage:
    from shared_models.logging import configure_logging, get_logger, LogEventType

    # In service main.py
    configure_logging(
        service_name="rest_service",
        log_level=settings.LOG_LEVEL,
        json_format=True
    )

    # In any module
    logger = get_logger(__name__)
    logger.info("Processing request", event_type=LogEventType.REQUEST_IN, user_id=42)
"""

import logging
import sys
from contextvars import ContextVar
from enum import Enum
from typing import Any

import structlog

correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)
user_id_ctx: ContextVar[int | None] = ContextVar("user_id", default=None)


class LogEventType(str, Enum):
    """Event types for filtering in Loki/Grafana."""

    # HTTP/API events
    REQUEST_IN = "request_in"
    REQUEST_OUT = "request_out"
    RESPONSE = "response"

    # Job events
    JOB_START = "job_start"
    JOB_END = "job_end"
    JOB_ERROR = "job_error"
    JOB_SCHEDULED = "job_scheduled"

    # Queue events
    QUEUE_PUSH = "queue_push"
    QUEUE_POP = "queue_pop"

    # Tool events
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"

    # LLM events
    LLM_CALL = "llm_call"
    LLM_RESPONSE = "llm_response"

    # Memory events
    MEMORY_SAVE = "memory_save"
    MEMORY_RETRIEVE = "memory_retrieve"
    MEMORY_SEARCH = "memory_search"

    # Message events
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_PROCESSED = "message_processed"
    MESSAGE_SENT = "message_sent"

    # General events
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"
    STARTUP = "startup"
    SHUTDOWN = "shutdown"


class LogLevel(str, Enum):
    """Log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


def _add_correlation_id(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Processor to add correlation_id from context."""
    cid = correlation_id_ctx.get()
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict


def _add_user_id(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Processor to add user_id from context."""
    uid = user_id_ctx.get()
    if uid is not None:
        event_dict.setdefault("user_id", uid)
    return event_dict


def _make_service_processor(service_name: str):
    """Factory for processor that adds service name."""

    def processor(
        logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
    ) -> dict[str, Any]:
        event_dict["service"] = service_name
        return event_dict

    return processor


def _normalize_event_type(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Convert LogEventType enum to string if present."""
    event_type = event_dict.get("event_type")
    if isinstance(event_type, LogEventType):
        event_dict["event_type"] = event_type.value
    return event_dict


def configure_logging(
    service_name: str,
    log_level: str = "INFO",
    json_format: bool = True,
) -> None:
    """
    Configure structlog for a service.

    Args:
        service_name: Service name (assistant_service, rest_service, etc.)
        log_level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_format: True for JSON (production), False for console (development)
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        _add_correlation_id,
        _add_user_id,
        _make_service_processor(service_name),
        _normalize_event_type,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.CallsiteParameterAdder(
            parameters={
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.LINENO,
                structlog.processors.CallsiteParameter.FUNC_NAME,
            }
        ),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if json_format:
        shared_processors.append(structlog.processors.JSONRenderer())
    else:
        shared_processors.append(
            structlog.dev.ConsoleRenderer(colors=True, sort_keys=True)
        )

    structlog.configure(
        processors=shared_processors,
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a configured logger instance."""
    return structlog.get_logger(name)


def set_correlation_id(cid: str) -> None:
    """Set correlation_id for current context."""
    correlation_id_ctx.set(cid)


def get_correlation_id() -> str | None:
    """Get current correlation_id."""
    return correlation_id_ctx.get()


def clear_correlation_id() -> None:
    """Clear correlation_id from context."""
    correlation_id_ctx.set(None)


def set_user_id(user_id: int) -> None:
    """Set user_id for current context."""
    user_id_ctx.set(user_id)


def get_user_id() -> int | None:
    """Get current user_id."""
    return user_id_ctx.get()


def clear_user_id() -> None:
    """Clear user_id from context."""
    user_id_ctx.set(None)


def clear_context() -> None:
    """Clear all context variables."""
    clear_correlation_id()
    clear_user_id()
