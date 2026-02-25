"""Repository data models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, HttpUrl


class Repository(BaseModel):
    """Repository configuration model."""

    id: str
    organization: str
    project: str
    repository_name: str
    repository_url: HttpUrl
    service_hook_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class RepositoryCreate(BaseModel):
    """Repository creation request model."""

    repository_url: HttpUrl
