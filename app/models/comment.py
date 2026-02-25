"""Comment data models."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class CommentSeverity(str, Enum):
    """Severity level of a code review comment."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class CommentCategory(str, Enum):
    """Category of code review comment."""

    CODE_SMELL = "code_smell"
    BUG = "bug"
    SECURITY = "security"
    BEST_PRACTICE = "best_practice"
    ARCHITECTURE = "architecture"


class LineComment(BaseModel):
    """Line-level code review comment."""

    file_path: str
    line_number: int
    severity: CommentSeverity
    category: CommentCategory
    message: str
    suggestion: Optional[str] = None
    code_example: Optional[str] = None


class SummaryComment(BaseModel):
    """High-level architectural summary comment."""

    message: str
    solid_violations: List[str] = []
    design_patterns_identified: List[str] = []
    design_pattern_suggestions: List[str] = []
    architectural_issues: List[str] = []
