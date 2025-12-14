"""Error handling utilities for assistants"""

from typing import Any

from shared_models import get_logger

logger = get_logger(__name__)


class AssistantError(Exception):
    """Base exception for all assistant-related errors"""

    def __init__(self, message: str, assistant_name: str | None = None):
        self.assistant_name = assistant_name
        super().__init__(f"[{assistant_name or 'Unknown'}] {message}")


class ToolError(Exception):
    """Base exception for all tool-related errors"""

    def __init__(
        self,
        message: str,
        tool_name: str | None = None,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.tool_name = tool_name
        self.error_code = error_code
        self.details = details or {}
        super().__init__(f"[{tool_name or 'Unknown'}] {message} (code: {error_code})")


class MessageProcessingError(AssistantError):
    """Raised when an assistant fails to process a message"""


class ToolExecutionError(ToolError):
    """Raised when a tool fails to execute"""


class InvalidInputError(Exception):
    """Raised when input validation fails"""


class ConfigurationError(Exception):
    """Raised when there is a configuration error"""


class ModelError(AssistantError):
    """Error raised when the language model fails"""


class ValidationError(AssistantError):
    """Error raised when input validation fails"""


class RateLimitError(AssistantError):
    """Error raised when rate limits are exceeded"""


def handle_assistant_error(error: Exception, assistant_name: str | None = None) -> str:
    """Handle assistant errors and return user-friendly message

    Args:
        error: The exception that occurred
        assistant_name: Name of the assistant where error occurred

    Returns:
        User-friendly error message
    """
    if isinstance(error, AssistantError):
        return f"Ошибка ассистента: {str(error)}"
    elif isinstance(error, ToolError):
        return f"Ошибка инструмента: {str(error)}"
    else:
        return "Произошла внутренняя ошибка. Пожалуйста, попробуйте позже."


def handle_error(error: Exception, context: dict[str, Any]) -> dict[str, Any]:
    """Handle errors and return structured response"""
    error_message = handle_assistant_error(error, context.get("assistant_name"))
    return {"status": "error", "response": None, "error": error_message}


def is_retryable_error(error: Exception) -> bool:
    """
    Check if an error should trigger a retry

    Args:
        error: The exception to check

    Returns:
        True if the error should trigger a retry
    """
    retryable_errors = (
        RateLimitError,
        ConnectionError,
        TimeoutError,
        # Add more retryable errors as needed
    )
    return isinstance(error, retryable_errors)
