import asyncio
from typing import TypeVar, Callable, Any, Optional
from config.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')

class RetryError(Exception):
    """Exception raised when all retry attempts are exhausted"""
    def __init__(self, last_error: Exception, attempts: int):
        self.last_error = last_error
        self.attempts = attempts
        super().__init__(f"Failed after {attempts} attempts. Last error: {str(last_error)}")

async def with_retry(
    func: Callable[..., Any],
    *args,
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    context: Optional[dict] = None,
    **kwargs
) -> T:
    """
    Execute a function with retry mechanism
    
    Args:
        func: Function to execute
        *args: Positional arguments for the function
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch and retry
        context: Additional context for logging
        **kwargs: Keyword arguments for the function
        
    Returns:
        Result of the function execution
        
    Raises:
        RetryError: If all retry attempts are exhausted
    """
    last_error = None
    current_delay = delay
    
    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except exceptions as e:
            last_error = e
            if attempt < max_attempts - 1:
                log_context = {
                    "attempt": attempt + 1,
                    "max_attempts": max_attempts,
                    "delay": current_delay,
                    "error": str(e)
                }
                if context:
                    log_context.update(context)
                    
                logger.warning("Retry attempt failed", **log_context)
                await asyncio.sleep(current_delay)
                current_delay *= backoff
            else:
                logger.error("All retry attempts failed",
                           attempts=max_attempts,
                           last_error=str(e),
                           **(context or {}))
                raise RetryError(last_error, max_attempts) 