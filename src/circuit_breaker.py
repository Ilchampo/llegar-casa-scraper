"""Circuit breaker implementation for resilient service calls."""

import asyncio
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Any, Optional
from dataclasses import dataclass, field

from .logging_config import get_logger


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5          # Number of failures before opening
    recovery_timeout: int = 60          # Seconds before trying half-open
    success_threshold: int = 3          # Successes needed to close from half-open
    timeout: int = 30                   # Call timeout in seconds
    
    
@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    circuit_opened_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading failures.
    
    States:
    - CLOSED: Normal operation, calls pass through
    - OPEN: Service is failing, calls are rejected immediately
    - HALF_OPEN: Testing if service recovered, limited calls allowed
    """
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.stats = CircuitBreakerStats()
        self.last_failure_time: Optional[float] = None
        self.logger = get_logger(f"circuit_breaker.{name}")
        
        self.logger.info(
            "Circuit breaker initialized",
            extra={
                "circuit_name": name,
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout
            }
        )
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function call through circuit breaker.
        
        Args:
            func: Async function to call
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpenException: When circuit is open
            Original exception: When function fails
        """
        self.stats.total_calls += 1
        
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._transition_to_half_open()
            else:
                self.logger.warning(
                    "Circuit breaker is OPEN, rejecting call",
                    extra={
                        "circuit_name": self.name,
                        "consecutive_failures": self.stats.consecutive_failures,
                        "last_failure_time": self.stats.last_failure_time.isoformat() if self.stats.last_failure_time else None
                    }
                )
                raise CircuitBreakerOpenException(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Service failed {self.stats.consecutive_failures} consecutive times."
                )
        
        try:
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.config.timeout
            )
            
            await self._on_success()
            return result
            
        except asyncio.TimeoutError as e:
            self.logger.error(
                "Circuit breaker call timed out",
                extra={
                    "circuit_name": self.name,
                    "timeout": self.config.timeout
                }
            )
            await self._on_failure(e)
            raise
            
        except Exception as e:
            await self._on_failure(e)
            raise
    
    async def _on_success(self):
        """Handle successful call."""
        self.stats.successful_calls += 1
        self.stats.consecutive_successes += 1
        self.stats.consecutive_failures = 0
        self.stats.last_success_time = datetime.now()
        
        if self.state == CircuitState.HALF_OPEN:
            if self.stats.consecutive_successes >= self.config.success_threshold:
                self._transition_to_closed()
        
        self.logger.debug(
            "Circuit breaker call succeeded",
            extra={
                "circuit_name": self.name,
                "state": self.state.value,
                "consecutive_successes": self.stats.consecutive_successes
            }
        )
    
    async def _on_failure(self, exception: Exception):
        """Handle failed call."""
        self.stats.failed_calls += 1
        self.stats.consecutive_failures += 1
        self.stats.consecutive_successes = 0
        self.stats.last_failure_time = datetime.now()
        self.last_failure_time = time.time()
        
        self.logger.error(
            "Circuit breaker call failed",
            extra={
                "circuit_name": self.name,
                "state": self.state.value,
                "consecutive_failures": self.stats.consecutive_failures,
                "exception_type": type(exception).__name__,
                "exception_message": str(exception)
            }
        )
        
        if (self.state == CircuitState.CLOSED or self.state == CircuitState.HALF_OPEN):
            if self.stats.consecutive_failures >= self.config.failure_threshold:
                self._transition_to_open()
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        
        return time.time() - self.last_failure_time >= self.config.recovery_timeout
    
    def _transition_to_open(self):
        """Transition circuit to OPEN state."""
        self.state = CircuitState.OPEN
        self.stats.circuit_opened_count += 1
        
        self.logger.warning(
            "Circuit breaker opened due to failures",
            extra={
                "circuit_name": self.name,
                "consecutive_failures": self.stats.consecutive_failures,
                "circuit_opened_count": self.stats.circuit_opened_count
            }
        )
    
    def _transition_to_half_open(self):
        """Transition circuit to HALF_OPEN state."""
        self.state = CircuitState.HALF_OPEN
        self.stats.consecutive_successes = 0
        
        self.logger.info(
            "Circuit breaker transitioning to HALF_OPEN",
            extra={
                "circuit_name": self.name,
                "recovery_timeout": self.config.recovery_timeout
            }
        )
    
    def _transition_to_closed(self):
        """Transition circuit to CLOSED state."""
        self.state = CircuitState.CLOSED
        self.stats.consecutive_failures = 0
        
        self.logger.info(
            "Circuit breaker closed after successful recovery",
            extra={
                "circuit_name": self.name,
                "consecutive_successes": self.stats.consecutive_successes
            }
        )
    
    def get_status(self) -> dict:
        """Get current circuit breaker status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "stats": {
                "total_calls": self.stats.total_calls,
                "successful_calls": self.stats.successful_calls,
                "failed_calls": self.stats.failed_calls,
                "success_rate": (
                    self.stats.successful_calls / self.stats.total_calls * 100
                    if self.stats.total_calls > 0 else 0
                ),
                "consecutive_failures": self.stats.consecutive_failures,
                "consecutive_successes": self.stats.consecutive_successes,
                "circuit_opened_count": self.stats.circuit_opened_count,
                "last_failure_time": (
                    self.stats.last_failure_time.isoformat()
                    if self.stats.last_failure_time else None
                ),
                "last_success_time": (
                    self.stats.last_success_time.isoformat()
                    if self.stats.last_success_time else None
                )
            },
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout
            }
        }


class CircuitBreakerOpenException(Exception):
    """Exception raised when circuit breaker is open."""
    pass


_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str, config: CircuitBreakerConfig = None) -> CircuitBreaker:
    """Get or create a circuit breaker instance."""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name, config)
    return _circuit_breakers[name]


def get_all_circuit_breakers() -> dict[str, CircuitBreaker]:
    """Get all registered circuit breakers."""
    return _circuit_breakers.copy() 