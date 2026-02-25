"""Agent state and status data models."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel

from .ast_node import ASTNode
from .comment import LineComment, SummaryComment
from .file_change import FileChange
from .pr_event import PRMetadata


class AgentStatus(str, Enum):
    """Agent execution status."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class AgentState(BaseModel):
    """Complete state of a review agent."""

    agent_id: str
    pr_id: str
    pr_metadata: PRMetadata
    phase: str
    start_time: float
    end_time: Optional[float] = None
    changed_files: List[FileChange] = []
    parsed_asts: Dict[str, ASTNode] = {}
    line_comments: List[LineComment] = []
    summary_comment: Optional[SummaryComment] = None
    errors: List[str] = []


class AgentInfo(BaseModel):
    """Agent information for monitoring."""

    agent_id: str
    pr_id: str
    status: AgentStatus
    phase: str
    start_time: datetime
    elapsed_seconds: float
