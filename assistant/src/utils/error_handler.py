from typing import Dict, Any, Optional, Type
from src.config.logger import get_logger

logger = get_logger(__name__)

class AssistantError(Exception):
    """Base exception for all assistant-related errors"""
    def __init__(self, message: str, error_code: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)

class ToolError(AssistantError):
    """Error raised when a tool fails to execute"""
    pass

class ModelError(AssistantError):
    """Error raised when the language model fails"""
    pass

class ValidationError(AssistantError):
    """Error raised when input validation fails"""
    pass

class RateLimitError(AssistantError):
    """Error raised when rate limits are exceeded"""
    pass

def handle_error(error: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Handle an error and return a formatted error response
    
    Args:
        error: The exception that occurred
        context: Additional context for error handling
        
    Returns:
        Dict containing error information
    """
    error_context = context or {}
    
    if isinstance(error, AssistantError):
        error_code = error.error_code
        message = error.message
        details = error.details
    else:
        error_code = "INTERNAL_ERROR"
        message = "Произошла внутренняя ошибка"
        details = {"original_error": str(error)}
    
    log_context = {
        "error_code": error_code,
        "error_message": message,
        "error_details": details,
        **error_context
    }
    
    logger.error("Error occurred", **log_context)
    
    return {
        "status": "error",
        "error_code": error_code,
        "message": message,
        "details": details
    }

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