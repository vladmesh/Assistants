"""Unit tests for shared_models logging module."""

import json
import logging
import sys
from io import StringIO
from unittest.mock import patch

import structlog

from shared_models.logging import (
    LogEventType,
    LogLevel,
    clear_context,
    clear_correlation_id,
    clear_user_id,
    configure_logging,
    get_correlation_id,
    get_logger,
    get_user_id,
    set_correlation_id,
    set_user_id,
)


class TestCorrelationIdContext:
    """Tests for correlation_id context variable management."""

    def setup_method(self):
        """Clear context before each test."""
        clear_context()

    def teardown_method(self):
        """Clear context after each test."""
        clear_context()

    def test_set_and_get_correlation_id(self):
        """Test setting and getting correlation_id."""
        assert get_correlation_id() is None

        set_correlation_id("test-correlation-123")
        assert get_correlation_id() == "test-correlation-123"

    def test_clear_correlation_id(self):
        """Test clearing correlation_id."""
        set_correlation_id("test-id")
        assert get_correlation_id() == "test-id"

        clear_correlation_id()
        assert get_correlation_id() is None

    def test_correlation_id_context_isolation(self):
        """Test that correlation_id is properly isolated."""
        set_correlation_id("id-1")
        assert get_correlation_id() == "id-1"

        set_correlation_id("id-2")
        assert get_correlation_id() == "id-2"


class TestUserIdContext:
    """Tests for user_id context variable management."""

    def setup_method(self):
        """Clear context before each test."""
        clear_context()

    def teardown_method(self):
        """Clear context after each test."""
        clear_context()

    def test_set_and_get_user_id(self):
        """Test setting and getting user_id."""
        assert get_user_id() is None

        set_user_id(42)
        assert get_user_id() == 42

    def test_clear_user_id(self):
        """Test clearing user_id."""
        set_user_id(123)
        assert get_user_id() == 123

        clear_user_id()
        assert get_user_id() is None

    def test_user_id_zero_is_valid(self):
        """Test that user_id of 0 is a valid value (not None)."""
        set_user_id(0)
        assert get_user_id() == 0


class TestClearContext:
    """Tests for clear_context function."""

    def test_clear_context_clears_all(self):
        """Test that clear_context clears both correlation_id and user_id."""
        set_correlation_id("test-id")
        set_user_id(42)

        assert get_correlation_id() == "test-id"
        assert get_user_id() == 42

        clear_context()

        assert get_correlation_id() is None
        assert get_user_id() is None


class TestLogEventType:
    """Tests for LogEventType enum."""

    def test_event_types_are_strings(self):
        """Test that all event types are string values."""
        assert LogEventType.REQUEST_IN.value == "request_in"
        assert LogEventType.JOB_START.value == "job_start"
        assert LogEventType.QUEUE_PUSH.value == "queue_push"
        assert LogEventType.LLM_CALL.value == "llm_call"
        assert LogEventType.ERROR.value == "error"

    def test_event_type_string_inheritance(self):
        """Test that LogEventType inherits from str."""
        assert isinstance(LogEventType.INFO, str)
        assert LogEventType.INFO == "info"


class TestLogLevel:
    """Tests for LogLevel enum."""

    def test_log_levels_match_logging_module(self):
        """Test that log levels match standard logging levels."""
        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.WARNING.value == "WARNING"
        assert LogLevel.ERROR.value == "ERROR"
        assert LogLevel.CRITICAL.value == "CRITICAL"


class TestConfigureLogging:
    """Tests for configure_logging function."""

    def setup_method(self):
        """Reset structlog config before each test."""
        structlog.reset_defaults()
        clear_context()

    def teardown_method(self):
        """Clean up after tests."""
        structlog.reset_defaults()
        clear_context()

    def test_configure_logging_json_format(self):
        """Test that JSON format produces valid JSON output."""
        configure_logging(
            service_name="test_service",
            log_level="INFO",
            json_format=True,
        )

        output = StringIO()
        with patch.object(sys, "stdout", output):
            logger = get_logger("test")
            logger.info("test message", extra_field="value")

        log_output = output.getvalue().strip()
        assert log_output, "Log output should not be empty"

        log_data = json.loads(log_output)
        assert log_data["event"] == "test message"
        assert log_data["service"] == "test_service"
        assert log_data["extra_field"] == "value"
        assert "timestamp" in log_data
        assert log_data["level"] == "info"

    def test_configure_logging_console_format(self):
        """Test that console format produces human-readable output."""
        configure_logging(
            service_name="test_service",
            log_level="INFO",
            json_format=False,
        )

        output = StringIO()
        with patch.object(sys, "stdout", output):
            logger = get_logger("test")
            logger.info("test console message")

        log_output = output.getvalue()
        assert "test console message" in log_output

    def test_configure_logging_adds_service_name(self):
        """Test that service name is added to all logs."""
        configure_logging(
            service_name="my_service",
            log_level="INFO",
            json_format=True,
        )

        output = StringIO()
        with patch.object(sys, "stdout", output):
            logger = get_logger("test")
            logger.info("message")

        log_data = json.loads(output.getvalue().strip())
        assert log_data["service"] == "my_service"

    def test_configure_logging_sets_log_level(self):
        """Test that log level is configured correctly."""
        configure_logging(
            service_name="test_service",
            log_level="WARNING",
            json_format=True,
        )

        # Verify the standard logging level is set
        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING

    def test_configure_logging_adds_correlation_id(self):
        """Test that correlation_id from context is added to logs."""
        configure_logging(
            service_name="test_service",
            log_level="INFO",
            json_format=True,
        )

        set_correlation_id("corr-123")

        output = StringIO()
        with patch.object(sys, "stdout", output):
            logger = get_logger("test")
            logger.info("message with correlation")

        log_data = json.loads(output.getvalue().strip())
        assert log_data["correlation_id"] == "corr-123"

    def test_configure_logging_adds_user_id(self):
        """Test that user_id from context is added to logs."""
        configure_logging(
            service_name="test_service",
            log_level="INFO",
            json_format=True,
        )

        set_user_id(42)

        output = StringIO()
        with patch.object(sys, "stdout", output):
            logger = get_logger("test")
            logger.info("message with user")

        log_data = json.loads(output.getvalue().strip())
        assert log_data["user_id"] == 42

    def test_configure_logging_normalizes_event_type(self):
        """Test that LogEventType enum is converted to string."""
        configure_logging(
            service_name="test_service",
            log_level="INFO",
            json_format=True,
        )

        output = StringIO()
        with patch.object(sys, "stdout", output):
            logger = get_logger("test")
            logger.info("test", event_type=LogEventType.JOB_START)

        log_data = json.loads(output.getvalue().strip())
        assert log_data["event_type"] == "job_start"

    def test_configure_logging_adds_callsite_info(self):
        """Test that filename, line number, and function name are added."""
        configure_logging(
            service_name="test_service",
            log_level="INFO",
            json_format=True,
        )

        output = StringIO()
        with patch.object(sys, "stdout", output):
            logger = get_logger("test")
            logger.info("message")

        log_data = json.loads(output.getvalue().strip())
        assert "filename" in log_data
        assert "lineno" in log_data
        assert "func_name" in log_data


class TestGetLogger:
    """Tests for get_logger function."""

    def setup_method(self):
        """Configure logging before tests."""
        structlog.reset_defaults()
        configure_logging(
            service_name="test_service",
            log_level="DEBUG",
            json_format=True,
        )

    def teardown_method(self):
        """Clean up after tests."""
        structlog.reset_defaults()

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a structlog logger instance."""
        logger = get_logger("my_module")
        # structlog returns BoundLoggerLazyProxy which has BoundLogger interface
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")
        assert hasattr(logger, "debug")
        assert callable(logger.info)

    def test_logger_can_log_at_all_levels(self):
        """Test that logger can log at all standard levels."""
        logger = get_logger("test")

        output = StringIO()
        with patch.object(sys, "stdout", output):
            logger.debug("debug message")
            logger.info("info message")
            logger.warning("warning message")
            logger.error("error message")

        log_output = output.getvalue()
        assert "debug message" in log_output
        assert "info message" in log_output
        assert "warning message" in log_output
        assert "error message" in log_output

    def test_logger_accepts_extra_fields(self):
        """Test that logger accepts arbitrary extra fields."""
        logger = get_logger("test")

        output = StringIO()
        with patch.object(sys, "stdout", output):
            logger.info(
                "message",
                user_id=123,
                request_id="req-456",
                custom_field="custom_value",
            )

        log_data = json.loads(output.getvalue().strip())
        assert log_data["user_id"] == 123
        assert log_data["request_id"] == "req-456"
        assert log_data["custom_field"] == "custom_value"
