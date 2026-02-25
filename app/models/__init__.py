"""Data models for Azure DevOps PR Review Agent."""

from .agent import AgentInfo, AgentState, AgentStatus
from .analysis import (
    ArchitecturalIssue,
    DesignPattern,
    SOLIDViolation,
    CodeContext,
    AnalysisRule,
    CodeIssue,
)
from .api_response import PublishResult, ValidationResult, WebhookResponse
from .ast_node import ASTNode
from .comment import (
    CommentCategory,
    CommentSeverity,
    LineComment,
    SummaryComment,
)
from .error import ErrorRecord
from .file_change import ChangeType, FileChange, LineChange
from .pr_event import PREvent, PRMetadata
from .repository import Repository, RepositoryCreate

__all__ = [
    # Repository models
    "Repository",
    "RepositoryCreate",
    # PR event models
    "PREvent",
    "PRMetadata",
    # File change models
    "ChangeType",
    "LineChange",
    "FileChange",
    # AST models
    "ASTNode",
    # Comment models
    "CommentSeverity",
    "CommentCategory",
    "LineComment",
    "SummaryComment",
    # Agent models
    "AgentStatus",
    "AgentState",
    "AgentInfo",
    # Analysis models
    "SOLIDViolation",
    "DesignPattern",
    "ArchitecturalIssue",
    "CodeContext",
    "AnalysisRule",
    "CodeIssue",
    # Error models
    "ErrorRecord",
    # API response models
    "WebhookResponse",
    "PublishResult",
    "ValidationResult",
]
