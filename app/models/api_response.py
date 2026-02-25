"""API response data models."""

from typing import List, Optional

from pydantic import BaseModel


class WebhookResponse(BaseModel):
    """Response from webhook handler."""

    status: str
    message: str


class PublishResult(BaseModel):
    """Result of comment publishing operation."""

    success: bool
    published_count: int
    failed_count: int
    errors: List[str] = []


class ValidationResult(BaseModel):
    """Result of validation operation."""

    valid: bool
    error_message: Optional[str] = None
