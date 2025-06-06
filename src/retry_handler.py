"""Smart retry handler with exponential backoff and jitter."""

import asyncio
import random
from datetime import datetime
from typing import Callable, Any, Type, List
from dataclasses import dataclass
from enum import Enum

from .logging_config import get_logger


class RetryCondition(Enum):
    """Conditions that determine if a retry should be attempted."""
    ALWAYS = "always"
    NEVER = "never"
    ON_TIMEOUT = "on_timeout"
    ON_CONNECTION_ERROR = "on_connection_error"
    ON_SERVER_ERROR = "on_server_error"
    ON_INCAPSULA_BLOCK = "on_incapsula_block"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0          # Base delay in seconds
    max_delay: float = 60.0          # Maximum delay in seconds
    exponential_base: float = 2.0    # Exponential backoff multiplier
    jitter: bool = True              # Add random jitter to prevent thundering herd
    jitter_range: float = 0.1        # Jitter range (±10% by default)
    retry_on: List[Type[Exception]] = None  # Exception types to retry on
    stop_on: List[Type[Exception]] = None   # Exception types to never retry on


class RetryHandler:
    """
    Smart retry handler with exponential backoff and jitter.
    
    Features:
    - Exponential backoff with configurable base and max delays
    - Jitter to prevent thundering herd problems
    - Conditional retries based on exception types
    - Comprehensive logging and metrics
    """
    
    def __init__(self, name: str, config: RetryConfig = None):
        self.name = name
        self.config = config or RetryConfig()
        self.logger = get_logger(f"retry.{name}")
        self.stats = {
            "total_attempts": 0,
            "successful_attempts": 0,
            "failed_attempts": 0,
            "total_retries": 0,
            "average_attempts": 0.0
        }
        
        if self.config.retry_on is None:
            self.config.retry_on = [
                ConnectionError,
                TimeoutError,
                asyncio.TimeoutError,
            ]
        
        if self.config.stop_on is None:
            self.config.stop_on = [
                ValueError,
                TypeError,
                KeyboardInterrupt,
            ]
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with retry logic.
        
        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: Last exception if all retries failed
        """
        attempt = 0
        last_exception = None
        start_time = datetime.now()
        
        while attempt < self.config.max_attempts:
            attempt += 1
            self.stats["total_attempts"] += 1
            
            try:
                self.logger.debug(
                    f"Executing function (attempt {attempt}/{self.config.max_attempts})",
                    extra={
                        "retry_handler": self.name,
                        "attempt": attempt,
                        "max_attempts": self.config.max_attempts
                    }
                )
                
                result = await func(*args, **kwargs)
                
                self.stats["successful_attempts"] += 1
                execution_time = (datetime.now() - start_time).total_seconds()
                
                if attempt > 1:
                    self.logger.info(
                        f"Function succeeded after {attempt} attempts",
                        extra={
                            "retry_handler": self.name,
                            "total_attempts": attempt,
                            "execution_time_seconds": round(execution_time, 2),
                            "retries_used": attempt - 1
                        }
                    )
                
                self._update_average_attempts()
                return result
                
            except Exception as e:
                last_exception = e
                
                self.logger.warning(
                    f"Function failed on attempt {attempt}: {str(e)}",
                    extra={
                        "retry_handler": self.name,
                        "attempt": attempt,
                        "exception_type": type(e).__name__,
                        "exception_message": str(e)
                    }
                )
                
                if not self._should_retry(e, attempt):
                    break
                
                if attempt < self.config.max_attempts:
                    delay = self._calculate_delay(attempt)
                    
                    self.logger.info(
                        f"Retrying in {delay:.2f} seconds",
                        extra={
                            "retry_handler": self.name,
                            "attempt": attempt,
                            "delay_seconds": round(delay, 2),
                            "next_attempt": attempt + 1
                        }
                    )
                    
                    await asyncio.sleep(delay)
                    self.stats["total_retries"] += 1
        
        self.stats["failed_attempts"] += 1
        self._update_average_attempts()
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        self.logger.error(
            f"Function failed after {attempt} attempts",
            extra={
                "retry_handler": self.name,
                "total_attempts": attempt,
                "execution_time_seconds": round(execution_time, 2),
                "final_exception_type": type(last_exception).__name__,
                "final_exception_message": str(last_exception)
            }
        )
        
        raise last_exception
    
    def _should_retry(self, exception: Exception, attempt: int) -> bool:
        """
        Determine if we should retry based on the exception and current attempt.
        """
        if attempt >= self.config.max_attempts:
            return False
        
        for stop_exception_type in self.config.stop_on:
            if isinstance(exception, stop_exception_type):
                self.logger.debug(
                    f"Not retrying due to stop condition: {type(exception).__name__}",
                    extra={
                        "retry_handler": self.name,
                        "exception_type": type(exception).__name__
                    }
                )
                return False
        
        for retry_exception_type in self.config.retry_on:
            if isinstance(exception, retry_exception_type):
                self.logger.debug(
                    f"Retrying due to retryable exception: {type(exception).__name__}",
                    extra={
                        "retry_handler": self.name,
                        "exception_type": type(exception).__name__
                    }
                )
                return True
        
        self.logger.debug(
            f"Not retrying unknown exception type: {type(exception).__name__}",
            extra={
                "retry_handler": self.name,
                "exception_type": type(exception).__name__
            }
        )
        return False
    
    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for the given attempt using exponential backoff with jitter.
        """
        delay = self.config.base_delay * (self.config.exponential_base ** (attempt - 1))
        
        delay = min(delay, self.config.max_delay)
        
        if self.config.jitter:
            jitter_amount = delay * self.config.jitter_range
            jitter = random.uniform(-jitter_amount, jitter_amount)
            delay += jitter
            delay = max(0.1, delay)
        
        return delay
    
    def _update_average_attempts(self):
        """Update average attempts statistic."""
        total_executions = self.stats["successful_attempts"] + self.stats["failed_attempts"]
        if total_executions > 0:
            self.stats["average_attempts"] = self.stats["total_attempts"] / total_executions
    
    def get_stats(self) -> dict:
        """Get retry handler statistics."""
        return {
            "name": self.name,
            "config": {
                "max_attempts": self.config.max_attempts,
                "base_delay": self.config.base_delay,
                "max_delay": self.config.max_delay,
                "exponential_base": self.config.exponential_base,
                "jitter": self.config.jitter
            },
            "stats": self.stats.copy()
        }


class RetryConfigs:
    """Predefined retry configurations for common use cases."""
    
    CONSERVATIVE = RetryConfig(
        max_attempts=2,
        base_delay=2.0,
        max_delay=10.0,
        exponential_base=2.0
    )
    
    STANDARD = RetryConfig(
        max_attempts=3,
        base_delay=1.0,
        max_delay=30.0,
        exponential_base=2.0
    )
    
    AGGRESSIVE = RetryConfig(
        max_attempts=5,
        base_delay=0.5,
        max_delay=60.0,
        exponential_base=1.5
    )
    
    WEB_SCRAPING = RetryConfig(
        max_attempts=3,
        base_delay=2.0,
        max_delay=30.0,
        exponential_base=2.0,
        retry_on=[
            ConnectionError,
            TimeoutError,
            asyncio.TimeoutError,
            OSError,
        ],
        stop_on=[
            ValueError,
            TypeError,
            KeyboardInterrupt,
        ]
    )


_retry_handlers: dict[str, RetryHandler] = {}


def get_retry_handler(name: str, config: RetryConfig = None) -> RetryHandler:
    """Get or create a retry handler instance."""
    if name not in _retry_handlers:
        _retry_handlers[name] = RetryHandler(name, config)
    return _retry_handlers[name]


def get_all_retry_handlers() -> dict[str, RetryHandler]:
    """Get all registered retry handlers."""
    return _retry_handlers.copy()


def with_retry(
    name: str,
    config: RetryConfig = None,
    handler: RetryHandler = None
):
    """
    Decorator to add retry functionality to async functions.
    
    Args:
        name: Name for the retry handler (used for logging and metrics)
        config: Retry configuration (optional)
        handler: Existing retry handler to use (optional)
    """
    def decorator(func: Callable):
        retry_handler = handler or get_retry_handler(name, config)
        
        async def wrapper(*args, **kwargs):
            return await retry_handler.execute(func, *args, **kwargs)
        
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        wrapper.retry_handler = retry_handler
        
        return wrapper
    
    return decorator 