"""
Unit tests for structured logging utilities.
"""

import json
import logging
from io import StringIO

import pytest

from app.utils.logging import (
    setup_logging,
    get_logger,
    JSONFormatter,
    log_pr_event,
    log_phase_transition,
    log_api_call,
)


def test_json_formatter():
    """Test JSON formatter produces valid JSON output."""
    # Create formatter
    formatter = JSONFormatter()
    
    # Create log record
    logger = logging.getLogger("test")
    logger.setLevel(logging.INFO)
    
    # Create string buffer to capture output
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Log a message
    logger.info("Test message", extra={"agent_id": "agent_123", "pr_id": "456"})
    
    # Get output
    output = stream.getvalue()
    
    # Parse JSON
    log_data = json.loads(output)
    
    # Verify structure
    assert "timestamp" in log_data
    assert log_data["level"] == "INFO"
    assert log_data["logger"] == "test"
    assert log_data["message"] == "Test message"
    assert log_data["agent_id"] == "agent_123"
    assert log_data["pr_id"] == "456"
    assert "source" in log_data


def test_get_logger_with_context():
    """Test getting logger with context."""
    logger = get_logger("test_module", agent_id="agent_123", pr_id="456")
    
    assert logger.extra["agent_id"] == "agent_123"
    assert logger.extra["pr_id"] == "456"


def test_log_pr_event():
    """Test PR event logging."""
    logger = get_logger("test")
    
    # Create string buffer to capture output
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger.logger.addHandler(handler)
    logger.logger.setLevel(logging.INFO)
    
    # Log PR event
    log_pr_event(logger, pr_id="123", repository_id="repo_456", event_type="git.pullrequest.created")
    
    # Get output
    output = stream.getvalue()
    log_data = json.loads(output)
    
    # Verify
    assert log_data["pr_id"] == "123"
    assert log_data["repository_id"] == "repo_456"
    assert "event_type" in log_data["context"]


def test_log_phase_transition():
    """Test phase transition logging."""
    logger = get_logger("test")
    
    # Create string buffer to capture output
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger.logger.addHandler(handler)
    logger.logger.setLevel(logging.INFO)
    
    # Log phase transition
    log_phase_transition(logger, agent_id="agent_123", pr_id="456", phase="initialize", status="started")
    
    # Get output
    output = stream.getvalue()
    log_data = json.loads(output)
    
    # Verify
    assert log_data["agent_id"] == "agent_123"
    assert log_data["pr_id"] == "456"
    assert log_data["phase"] == "initialize"
    assert "status" in log_data["context"]


def test_log_api_call():
    """Test API call logging."""
    logger = get_logger("test")
    
    # Create string buffer to capture output
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger.logger.addHandler(handler)
    logger.logger.setLevel(logging.INFO)
    
    # Log API call
    log_api_call(
        logger,
        service="azure_devops",
        endpoint="/api/pullrequests/123",
        method="GET",
        status_code=200,
        duration_ms=150.5
    )
    
    # Get output
    output = stream.getvalue()
    log_data = json.loads(output)
    
    # Verify
    assert "service" in log_data["context"]
    assert "endpoint" in log_data["context"]
    assert "method" in log_data["context"]
    assert "status_code" in log_data["context"]
    assert "duration_ms" in log_data["context"]


def test_log_api_call_with_error():
    """Test API call logging with error."""
    logger = get_logger("test")
    
    # Create string buffer to capture output
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger.logger.addHandler(handler)
    logger.logger.setLevel(logging.ERROR)
    
    # Log API call with error
    log_api_call(
        logger,
        service="azure_devops",
        endpoint="/api/pullrequests/123",
        method="GET",
        error="Connection timeout"
    )
    
    # Get output
    output = stream.getvalue()
    log_data = json.loads(output)
    
    # Verify
    assert log_data["level"] == "ERROR"
    assert "error" in log_data["context"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
