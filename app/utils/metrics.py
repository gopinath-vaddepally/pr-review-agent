"""
Metrics collection and emission for observability.

This module provides metrics tracking for:
- Agent execution time
- Number of comments generated
- API call latency
- Storage in agent_executions table
"""

import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from app.utils.logging import get_logger

logger = get_logger(__name__)


class MetricsCollector:
    """
    Collects metrics during agent execution.
    
    Tracks:
    - Execution start/end time
    - Line comments count
    - Summary comment generation
    - API call counts and latency
    - Errors
    """
    
    def __init__(self, agent_id: str, pr_id: str, repository_id: str):
        """
        Initialize metrics collector.
        
        Args:
            agent_id: Agent ID
            pr_id: Pull request ID
            repository_id: Repository ID
        """
        self.agent_id = agent_id
        self.pr_id = pr_id
        self.repository_id = repository_id
        
        # Timing metrics
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.duration_ms: Optional[int] = None
        
        # Analysis metrics
        self.line_comments_count: int = 0
        self.summary_comment_generated: bool = False
        self.files_analyzed: int = 0
        
        # API metrics
        self.api_calls: Dict[str, int] = {}
        self.api_latencies: Dict[str, list[float]] = {}
        
        # Status
        self.status: str = "running"
        self.error_message: Optional[str] = None
    
    def start(self) -> None:
        """Mark agent execution start."""
        self.start_time = datetime.now(timezone.utc)
        self.status = "running"
        logger.info(
            f"Metrics collection started for agent {self.agent_id}",
            extra={
                "agent_id": self.agent_id,
                "pr_id": self.pr_id,
                "repository_id": self.repository_id,
            }
        )
    
    def complete(self, status: str = "completed", error_message: Optional[str] = None) -> None:
        """
        Mark agent execution completion.
        
        Args:
            status: Final status ('completed', 'failed', 'timeout')
            error_message: Error message if failed
        """
        self.end_time = datetime.now(timezone.utc)
        self.status = status
        self.error_message = error_message
        
        if self.start_time:
            duration = (self.end_time - self.start_time).total_seconds()
            self.duration_ms = int(duration * 1000)
        
        logger.info(
            f"Metrics collection completed for agent {self.agent_id}",
            extra={
                "agent_id": self.agent_id,
                "pr_id": self.pr_id,
                "status": self.status,
                "duration_ms": self.duration_ms,
                "line_comments_count": self.line_comments_count,
                "summary_comment_generated": self.summary_comment_generated,
                "files_analyzed": self.files_analyzed,
            }
        )
    
    def record_line_comments(self, count: int) -> None:
        """
        Record number of line comments generated.
        
        Args:
            count: Number of line comments
        """
        self.line_comments_count = count
    
    def record_summary_comment(self, generated: bool = True) -> None:
        """
        Record summary comment generation.
        
        Args:
            generated: Whether summary comment was generated
        """
        self.summary_comment_generated = generated
    
    def record_files_analyzed(self, count: int) -> None:
        """
        Record number of files analyzed.
        
        Args:
            count: Number of files
        """
        self.files_analyzed = count
    
    def record_api_call(self, service: str, duration_ms: float) -> None:
        """
        Record API call and latency.
        
        Args:
            service: Service name (e.g., 'azure_devops', 'openai')
            duration_ms: Call duration in milliseconds
        """
        # Increment call count
        self.api_calls[service] = self.api_calls.get(service, 0) + 1
        
        # Record latency
        if service not in self.api_latencies:
            self.api_latencies[service] = []
        self.api_latencies[service].append(duration_ms)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get summary of collected metrics.
        
        Returns:
            Dictionary of metrics
        """
        summary = {
            "agent_id": self.agent_id,
            "pr_id": self.pr_id,
            "repository_id": self.repository_id,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "line_comments_count": self.line_comments_count,
            "summary_comment_generated": self.summary_comment_generated,
            "files_analyzed": self.files_analyzed,
            "api_calls": self.api_calls,
        }
        
        # Add API latency statistics
        if self.api_latencies:
            latency_stats = {}
            for service, latencies in self.api_latencies.items():
                if latencies:
                    latency_stats[service] = {
                        "count": len(latencies),
                        "min_ms": round(min(latencies), 2),
                        "max_ms": round(max(latencies), 2),
                        "avg_ms": round(sum(latencies) / len(latencies), 2),
                    }
            summary["api_latencies"] = latency_stats
        
        if self.error_message:
            summary["error_message"] = self.error_message
        
        return summary
    
    async def save_to_database(self, db_connection) -> None:
        """
        Save metrics to agent_executions table.
        
        Args:
            db_connection: Database connection
        """
        try:
            query = """
                INSERT INTO agent_executions (
                    agent_id, pr_id, repository_id, status,
                    start_time, end_time, duration_ms,
                    line_comments_count, summary_comment_generated,
                    error_message
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON DUPLICATE KEY UPDATE
                    status = VALUES(status),
                    end_time = VALUES(end_time),
                    duration_ms = VALUES(duration_ms),
                    line_comments_count = VALUES(line_comments_count),
                    summary_comment_generated = VALUES(summary_comment_generated),
                    error_message = VALUES(error_message)
            """
            
            async with db_connection.cursor() as cursor:
                await cursor.execute(
                    query,
                    (
                        self.agent_id,
                        self.pr_id,
                        self.repository_id,
                        self.status,
                        self.start_time,
                        self.end_time,
                        self.duration_ms,
                        self.line_comments_count,
                        self.summary_comment_generated,
                        self.error_message,
                    )
                )
                await db_connection.commit()
            
            logger.info(
                f"Metrics saved to database for agent {self.agent_id}",
                extra={"agent_id": self.agent_id, "pr_id": self.pr_id}
            )
        
        except Exception as e:
            logger.error(
                f"Failed to save metrics to database for agent {self.agent_id}",
                extra={"agent_id": self.agent_id, "pr_id": self.pr_id, "error": str(e)},
                exc_info=True
            )


@asynccontextmanager
async def track_api_call(
    metrics_collector: Optional[MetricsCollector],
    service: str,
    logger_adapter
):
    """
    Context manager to track API call timing.
    
    Usage:
        async with track_api_call(metrics, "azure_devops", logger):
            result = await api_client.get_pr(pr_id)
    
    Args:
        metrics_collector: Metrics collector (optional)
        service: Service name
        logger_adapter: Logger for logging API calls
        
    Yields:
        None
    """
    start_time = time.time()
    error = None
    
    try:
        yield
    except Exception as e:
        error = e
        raise
    finally:
        duration_ms = (time.time() - start_time) * 1000
        
        # Record in metrics
        if metrics_collector:
            metrics_collector.record_api_call(service, duration_ms)
        
        # Log API call
        from app.utils.logging import log_api_call
        log_api_call(
            logger_adapter,
            service=service,
            endpoint="",  # Can be enhanced to include actual endpoint
            method="",    # Can be enhanced to include actual method
            duration_ms=duration_ms,
            error=str(error) if error else None
        )


def emit_metric(metric_name: str, value: float, **tags: Any) -> None:
    """
    Emit a metric (for future integration with monitoring systems).
    
    For hackathon, this logs the metric. In production, this could
    send to Prometheus, CloudWatch, DataDog, etc.
    
    Args:
        metric_name: Metric name
        value: Metric value
        **tags: Metric tags/labels
    """
    logger.info(
        f"Metric: {metric_name}",
        extra={
            "metric_name": metric_name,
            "metric_value": value,
            "metric_tags": tags,
        }
    )
