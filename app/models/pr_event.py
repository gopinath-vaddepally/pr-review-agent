"""Pull request event data models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PREvent(BaseModel):
    """Pull request event from Azure DevOps webhook."""

    event_type: str  # 'git.pullrequest.created', 'git.pullrequest.updated'
    pr_id: str
    repository_id: str
    source_branch: str
    target_branch: str
    author: str
    title: str
    description: Optional[str] = None
    timestamp: datetime


class PRMetadata(BaseModel):
    """Pull request metadata for agent processing."""

    pr_id: str
    repository_id: str
    source_branch: str
    target_branch: str
    author: str
    title: str
    description: Optional[str] = None
    source_commit_id: str
    target_commit_id: str
