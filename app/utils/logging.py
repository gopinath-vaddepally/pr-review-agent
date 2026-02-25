"""
Structured logging utilities with JSON formatting and context injection.

This module provides structured logging capabilities with:
- JSON formatted log output for machine-readable logs
- Context injection (agent_id, pr_id, phase) via LoggerAdapter
- Standardized log fields across all components
- Integration with Python's standard logging module
"""

import logging
import json
import sys
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional, MutableMapping
from logging import LogRecord


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    
    Outputs log records as JSON with standard fields:
    - timestamp: ISO 8601 formatted timestamp
    - level: Log level (INFO, WARNING, ERROR, etc.)
    - logger: Logger name
    - message: Log message
    - context: Additional context fields (agent_id, pr_id, phase, etc.)
    - error: Error details (for ERROR/CRITICAL levels)
    """
    
    def format(self, record: LogRecord) -> str:
        """
        Format log record as JSON.
        
        Args:
            record: Log record to format
            
        Returns:
            JSON formatted log string
        """
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add context fields from extra
        if hasattr(record, "agent_id"):
            log_data["agent_id"] = record.agent_id
        if hasattr(record, "pr_id"):
            log_data["pr_id"] = record.pr_id
        if hasattr(record, "phase"):
            log_data["phase"] = record.phase
        if hasattr(record, "repository_id"):
            log_data["repository_id"] = record.repository_id
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        
        # Add any other extra fields
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info",
                "agent_id", "pr_id", "phase", "repository_id", "request_id"
            ]:
                extra_fields[key] = value
        
        if extra_fields:
            log_data["context"] = extra_fields
        
        # Add exception info if present
        if record.exc_info:
            log_data["error"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "stack_trace": "".join(traceback.format_exception(*record.exc_info))
            }
        
        # Add source location
        log_data["source"] = {
            "file": record.pathname,
            "line": record.lineno,
            "function": record.funcName
        }
        
        return json.dumps(log_data)


class LogContext:
    """
    Context manager for adding temporary context to logs.
    
    Usage:
        with LogContext(logger, agent_id="agent_123", pr_id="456"):
            logger.info("Processing PR")  # Will include agent_id and pr_id
    """
    
    def __init__(self, logger: logging.LoggerAdapter, **context: Any):
        """
        Initialize log context.
        
        Args:
            logger: Logger adapter to add context to
            **context: Context fields to add
        """
        self.logger = logger
        self.context = context
        self.old_extra = None
    
    def __enter__(self) -> logging.LoggerAdapter:
        """Enter context and add fields to logger."""
        self.old_extra = self.logger.extra.copy() if self.logger.extra else {}
        self.logger.extra.update(self.context)
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and restore original logger state."""
        if self.old_extra is not None:
            self.logger.extra = self.old_extra


class ContextLoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter that injects context fields into all log records.
    
    This adapter allows setting context fields (agent_id, pr_id, phase)
    that will be automatically included in all log entries.
    """
    
    def __init__(self, logger: logging.Logger, extra: Optional[Dict[str, Any]] = None):
        """
        Initialize context logger adapter.
        
        Args:
            logger: Base logger
            extra: Initial context fields
        """
        super().__init__(logger, extra or {})
    
    def process(self, msg: str, kwargs: MutableMapping[str, Any]) -> tuple[str, MutableMapping[str, Any]]:
        """
        Process log message and inject context.
        
        Args:
            msg: Log message
            kwargs: Log kwargs
            
        Returns:
            Tuple of (message, kwargs) with context injected
        """
        # Merge extra fields
        extra = kwargs.get("extra", {})
        extra.update(self.extra)
        kwargs["extra"] = extra
        return msg, kwargs
    
    def with_context(self, **context: Any) -> "ContextLoggerAdapter":
        """
        Create a new logger adapter with additional context.
        
        Args:
            **context: Additional context fields
            
        Returns:
            New logger adapter with merged context
        """
        new_extra = self.extra.copy()
        new_extra.update(context)
        return ContextLoggerAdapter(self.logger, new_extra)


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure structured logging for the application.
    
    Sets up:
    - JSON formatter for all handlers
    - Console handler with appropriate log level
    - Root logger configuration
    
    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Create JSON formatter
    formatter = JSONFormatter()
    
    # Configure console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str, **context: Any) -> ContextLoggerAdapter:
    """
    Get a context-aware logger for a module.
    
    Args:
        name: Logger name (typically __name__)
        **context: Initial context fields (agent_id, pr_id, phase, etc.)
        
    Returns:
        Context logger adapter
        
    Example:
        logger = get_logger(__name__, agent_id="agent_123", pr_id="456")
        logger.info("Starting analysis")  # Will include agent_id and pr_id
    """
    base_logger = logging.getLogger(name)
    return ContextLoggerAdapter(base_logger, context)


def log_pr_event(logger: logging.LoggerAdapter, pr_id: str, repository_id: str, event_type: str) -> None:
    """
    Log PR event detection with required fields.
    
    Args:
        logger: Logger to use
        pr_id: Pull request ID
        repository_id: Repository ID
        event_type: Event type (e.g., 'git.pullrequest.created')
    """
    logger.info(
        f"PR event detected: {event_type}",
        extra={
            "pr_id": pr_id,
            "repository_id": repository_id,
            "event_type": event_type,
        }
    )


def log_phase_transition(
    logger: logging.LoggerAdapter,
    agent_id: str,
    pr_id: str,
    phase: str,
    status: str
) -> None:
    """
    Log agent phase transition (start or completion).
    
    Args:
        logger: Logger to use
        agent_id: Agent ID
        pr_id: Pull request ID
        phase: Phase name (e.g., 'initialize', 'retrieve_code', 'line_analysis')
        status: Status ('started' or 'completed')
    """
    logger.info(
        f"Agent phase {status}: {phase}",
        extra={
            "agent_id": agent_id,
            "pr_id": pr_id,
            "phase": phase,
            "status": status,
        }
    )


def log_api_call(
    logger: logging.LoggerAdapter,
    service: str,
    endpoint: str,
    method: str,
    status_code: Optional[int] = None,
    duration_ms: Optional[float] = None,
    error: Optional[str] = None
) -> None:
    """
    Log Azure DevOps API call with request/response details.
    
    Args:
        logger: Logger to use
        service: Service name (e.g., 'azure_devops', 'openai')
        endpoint: API endpoint
        method: HTTP method
        status_code: Response status code (if available)
        duration_ms: Request duration in milliseconds (if available)
        error: Error message (if request failed)
    """
    extra = {
        "service": service,
        "endpoint": endpoint,
        "method": method,
    }
    
    if status_code is not None:
        extra["status_code"] = status_code
    if duration_ms is not None:
        extra["duration_ms"] = round(duration_ms, 2)
    if error is not None:
        extra["error"] = error
    
    if error:
        logger.error(f"API call failed: {method} {endpoint}", extra=extra)
    else:
        logger.info(f"API call: {method} {endpoint}", extra=extra)


def log_error_with_context(
    logger: logging.LoggerAdapter,
    message: str,
    error: Exception,
    **context: Any
) -> None:
    """
    Log error with full stack trace and context.
    
    Args:
        logger: Logger to use
        message: Error message
        error: Exception object
        **context: Additional context fields
    """
    logger.error(
        message,
        extra=context,
        exc_info=True
    )
