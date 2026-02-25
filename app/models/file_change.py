"""File change data models."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class ChangeType(str, Enum):
    """Type of file change."""

    ADD = "add"
    EDIT = "edit"
    DELETE = "delete"


class LineChange(BaseModel):
    """Individual line change in a file."""

    line_number: int
    change_type: ChangeType
    content: str


class FileChange(BaseModel):
    """File change information with line-level details."""

    file_path: str
    change_type: ChangeType
    added_lines: List[LineChange]
    modified_lines: List[LineChange]
    deleted_lines: List[LineChange]
    source_content: Optional[str] = None
    target_content: Optional[str] = None
