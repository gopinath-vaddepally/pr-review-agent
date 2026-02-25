"""
Unit tests for metrics collection utilities.
"""

import pytest
from datetime import datetime

from app.utils.metrics import MetricsCollector, emit_metric


def test_metrics_collector_initialization():
    """Test metrics collector initialization."""
    collector = MetricsCollector(
        agent_id="agent_123",
        pr_id="456",
        repository_id="repo_789"
    )
    
    assert collector.agent_id == "agent_123"
    assert collector.pr_id == "456"
    assert collector.repository_id == "repo_789"
    assert collector.status == "running"
    assert collector.line_comments_count == 0
    assert collector.summary_comment_generated is False


def test_metrics_collector_start():
    """Test starting metrics collection."""
    collector = MetricsCollector("agent_123", "456", "repo_789")
    
    collector.start()
    
    assert collector.start_time is not None
    assert isinstance(collector.start_time, datetime)
    assert collector.status == "running"


def test_metrics_collector_complete():
    """Test completing metrics collection."""
    collector = MetricsCollector("agent_123", "456", "repo_789")
    
    collector.start()
    collector.complete(status="completed")
    
    assert collector.end_time is not None
    assert collector.status == "completed"
    assert collector.duration_ms is not None
    assert collector.duration_ms >= 0


def test_metrics_collector_complete_with_error():
    """Test completing metrics collection with error."""
    collector = MetricsCollector("agent_123", "456", "repo_789")
    
    collector.start()
    collector.complete(status="failed", error_message="Test error")
    
    assert collector.status == "failed"
    assert collector.error_message == "Test error"


def test_metrics_collector_record_line_comments():
    """Test recording line comments count."""
    collector = MetricsCollector("agent_123", "456", "repo_789")
    
    collector.record_line_comments(5)
    
    assert collector.line_comments_count == 5


def test_metrics_collector_record_summary_comment():
    """Test recording summary comment generation."""
    collector = MetricsCollector("agent_123", "456", "repo_789")
    
    collector.record_summary_comment(True)
    
    assert collector.summary_comment_generated is True


def test_metrics_collector_record_files_analyzed():
    """Test recording files analyzed count."""
    collector = MetricsCollector("agent_123", "456", "repo_789")
    
    collector.record_files_analyzed(10)
    
    assert collector.files_analyzed == 10


def test_metrics_collector_record_api_call():
    """Test recording API call metrics."""
    collector = MetricsCollector("agent_123", "456", "repo_789")
    
    collector.record_api_call("azure_devops", 150.5)
    collector.record_api_call("azure_devops", 200.0)
    collector.record_api_call("openai", 500.0)
    
    assert collector.api_calls["azure_devops"] == 2
    assert collector.api_calls["openai"] == 1
    assert len(collector.api_latencies["azure_devops"]) == 2
    assert len(collector.api_latencies["openai"]) == 1


def test_metrics_collector_get_summary():
    """Test getting metrics summary."""
    collector = MetricsCollector("agent_123", "456", "repo_789")
    
    collector.start()
    collector.record_line_comments(5)
    collector.record_summary_comment(True)
    collector.record_files_analyzed(3)
    collector.record_api_call("azure_devops", 150.0)
    collector.record_api_call("azure_devops", 200.0)
    collector.complete(status="completed")
    
    summary = collector.get_metrics_summary()
    
    assert summary["agent_id"] == "agent_123"
    assert summary["pr_id"] == "456"
    assert summary["repository_id"] == "repo_789"
    assert summary["status"] == "completed"
    assert summary["line_comments_count"] == 5
    assert summary["summary_comment_generated"] is True
    assert summary["files_analyzed"] == 3
    assert summary["duration_ms"] is not None
    assert "api_latencies" in summary
    assert "azure_devops" in summary["api_latencies"]
    assert summary["api_latencies"]["azure_devops"]["count"] == 2
    assert summary["api_latencies"]["azure_devops"]["avg_ms"] == 175.0


def test_emit_metric():
    """Test emitting a metric."""
    # This should not raise an exception
    emit_metric("test_metric", 42.0, tag1="value1", tag2="value2")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
