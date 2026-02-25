"""
Resilience utilities for error handling and fault tolerance.

This module provides:
- retry_with_backoff decorator for transient errors
- CircuitBreaker class for external service calls
- Error recovery and state management utilities
"""

import asyncio
import time
import logging
from typing import Callable, Any, Optional, TypeVar, ParamSpec
from functools import wraps
from enum import Enum

logger = logging.getLogger(__name__)

# Type variables for generic decorator
P = ParamSpec('P')
T = TypeVar('T')


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


class TransientError(Exception):
    """Base class for transient errors that should be retried."""
    pass


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying functions with exponential backoff.
    
    This decorator implements retry logic with exponential backoff for handling
    transient errors. It's designed to be applied to Azure DevOps API calls,
    Redis operations, and other external service interactions.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay in seconds between retries (default: 1.0)
        max_delay: Maximum delay in seconds between retries (default: 60.0)
        exponential_base: Base for exponential backoff calculation (default: 2.0)
        exceptions: Tuple of exception types to catch and retry (default: all exceptions)
    
    Returns:
        Decorated function with retry logic
    
    Example:
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        async def fetch_data():
            return await api_client.get_data()
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    result = await func(*args, **kwargs)
                    
                    if attempt > 0:
                        logger.info(
                            f"{func.__name__} succeeded on attempt {attempt + 1}/{max_retries}"
                        )
                    
                    return result
                
                except exceptions as e:
                    last_exception = e
                    
                    # Check if this is the last attempt
                    if attempt == max_retries - 1:
                        logger.error(
                            f"{func.__name__} failed after {max_retries} attempts: {e}",
                            exc_info=True
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    logger.warning(
                        f"{func.__name__} failed on attempt {attempt + 1}/{max_retries}: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    
                    await asyncio.sleep(delay)
            
            # This should never be reached, but just in case
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    result = func(*args, **kwargs)
                    
                    if attempt > 0:
                        logger.info(
                            f"{func.__name__} succeeded on attempt {attempt + 1}/{max_retries}"
                        )
                    
                    return result
                
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries - 1:
                        logger.error(
                            f"{func.__name__} failed after {max_retries} attempts: {e}",
                            exc_info=True
                        )
                        raise
                    
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    logger.warning(
                        f"{func.__name__} failed on attempt {attempt + 1}/{max_retries}: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    
                    time.sleep(delay)
            
            raise last_exception
        
        # Return appropriate wrapper based on whether function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for external service calls.
    
    The circuit breaker prevents cascading failures by:
    - Tracking failure rates for external service calls
    - Opening the circuit (rejecting requests) when failure threshold is exceeded
    - Periodically testing if the service has recovered (half-open state)
    - Closing the circuit when service is healthy again
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service is failing, requests are rejected immediately
    - HALF_OPEN: Testing if service recovered, limited requests allowed
    
    Args:
        failure_threshold: Number of consecutive failures before opening circuit (default: 5)
        timeout: Seconds to wait before attempting recovery (default: 60)
        half_open_max_calls: Max calls allowed in half-open state (default: 3)
    
    Example:
        circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=60)
        
        async def call_external_service():
            return await circuit_breaker.call(api_client.fetch_data)
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: int = 60,
        half_open_max_calls: int = 3
    ):
        """Initialize circuit breaker."""
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.half_open_max_calls = half_open_max_calls
        
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitState.CLOSED
        self.half_open_calls = 0
        
        logger.info(
            f"CircuitBreaker initialized: failure_threshold={failure_threshold}, "
            f"timeout={timeout}s"
        )
    
    async def call(self, func: Callable[[], T]) -> T:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Async function to execute
        
        Returns:
            Function result
        
        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Any exception raised by the function
        """
        # Check circuit state
        if self.state == CircuitState.OPEN:
            # Check if timeout has elapsed
            if self.last_failure_time and (time.time() - self.last_failure_time) > self.timeout:
                logger.info("Circuit breaker transitioning to HALF_OPEN state")
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is OPEN. Service unavailable. "
                    f"Will retry after {self.timeout}s timeout."
                )
        
        # In half-open state, limit number of calls
        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.half_open_max_calls:
                raise CircuitBreakerOpenError(
                    "Circuit breaker is HALF_OPEN and max test calls reached"
                )
            self.half_open_calls += 1
        
        # Execute the function
        try:
            result = await func()
            
            # Record success
            self._record_success()
            
            return result
        
        except Exception as e:
            # Record failure
            self._record_failure()
            
            raise
    
    def _record_success(self) -> None:
        """Record successful call."""
        self.success_count += 1
        
        if self.state == CircuitState.HALF_OPEN:
            # If we've had enough successful calls in half-open state, close the circuit
            if self.success_count >= self.half_open_max_calls:
                logger.info("Circuit breaker transitioning to CLOSED state (service recovered)")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self.half_open_calls = 0
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            if self.failure_count > 0:
                logger.debug(f"Circuit breaker: resetting failure count after success")
                self.failure_count = 0
    
    def _record_failure(self) -> None:
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            # Failure in half-open state means service still unhealthy
            logger.warning("Circuit breaker transitioning to OPEN state (service still failing)")
            self.state = CircuitState.OPEN
            self.success_count = 0
            self.half_open_calls = 0
        elif self.state == CircuitState.CLOSED:
            # Check if we've exceeded failure threshold
            if self.failure_count >= self.failure_threshold:
                logger.warning(
                    f"Circuit breaker transitioning to OPEN state "
                    f"(failure threshold {self.failure_threshold} exceeded)"
                )
                self.state = CircuitState.OPEN
                self.success_count = 0
    
    def get_state(self) -> CircuitState:
        """Get current circuit breaker state."""
        return self.state
    
    def reset(self) -> None:
        """Manually reset circuit breaker to closed state."""
        logger.info("Circuit breaker manually reset to CLOSED state")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        self.last_failure_time = None


class ErrorRecoveryManager:
    """
    Manager for error recovery and state persistence.
    
    Provides utilities for:
    - Persisting agent state after each phase
    - Handling partial failures (continue with available data)
    - Logging errors with full context
    """
    
    @staticmethod
    async def persist_state_safely(
        state_manager,
        state: Any,
        context: dict
    ) -> bool:
        """
        Safely persist state with error handling.
        
        Args:
            state_manager: State manager instance (e.g., RedisClient)
            state: State object to persist
            context: Context information for logging
        
        Returns:
            True if successful, False otherwise
        """
        try:
            await state_manager.save_agent_state(state)
            logger.debug(f"State persisted successfully: {context}")
            return True
        
        except Exception as e:
            logger.error(
                f"Failed to persist state: {e}",
                extra={
                    "context": context,
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            return False
    
    @staticmethod
    def handle_partial_failure(
        operation_name: str,
        total_items: int,
        successful_items: int,
        errors: list,
        context: dict
    ) -> None:
        """
        Log partial failure with context.
        
        Args:
            operation_name: Name of the operation
            total_items: Total number of items processed
            successful_items: Number of successful items
            errors: List of error messages
            context: Additional context information
        """
        failed_items = total_items - successful_items
        
        if failed_items > 0:
            logger.warning(
                f"Partial failure in {operation_name}: "
                f"{successful_items}/{total_items} succeeded, {failed_items} failed",
                extra={
                    "operation": operation_name,
                    "total_items": total_items,
                    "successful_items": successful_items,
                    "failed_items": failed_items,
                    "errors": errors[:10],  # Limit to first 10 errors
                    "context": context
                }
            )
        else:
            logger.info(
                f"{operation_name} completed successfully: {successful_items}/{total_items}",
                extra={
                    "operation": operation_name,
                    "total_items": total_items,
                    "context": context
                }
            )
    
    @staticmethod
    def log_error_with_context(
        error: Exception,
        phase: str,
        context: dict
    ) -> dict:
        """
        Log error with full context and return error record.
        
        Args:
            error: Exception that occurred
            phase: Current phase/operation name
            context: Context information
        
        Returns:
            Error record dictionary
        """
        import traceback
        from datetime import datetime
        
        error_record = {
            "phase": phase,
            "error_type": type(error).__name__,
            "message": str(error),
            "stack_trace": traceback.format_exc(),
            "timestamp": datetime.now().isoformat(),
            "context": context
        }
        
        logger.error(
            f"Error in {phase}: {error}",
            extra=error_record,
            exc_info=True
        )
        
        return error_record


# Convenience function for creating circuit breakers with common configurations
def create_azure_devops_circuit_breaker() -> CircuitBreaker:
    """Create circuit breaker configured for Azure DevOps API calls."""
    return CircuitBreaker(
        failure_threshold=5,
        timeout=60,
        half_open_max_calls=3
    )


def create_llm_circuit_breaker() -> CircuitBreaker:
    """Create circuit breaker configured for LLM API calls."""
    return CircuitBreaker(
        failure_threshold=3,
        timeout=30,
        half_open_max_calls=2
    )


def create_redis_circuit_breaker() -> CircuitBreaker:
    """Create circuit breaker configured for Redis operations."""
    return CircuitBreaker(
        failure_threshold=5,
        timeout=10,
        half_open_max_calls=3
    )
