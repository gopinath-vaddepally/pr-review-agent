"""Error tracking data models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ErrorRecord(BaseModel):
    """Error record for tracking failures."""

    phase: str
    error_type: str
    message: str
    stack_trace: Optional[str] = None
    timestamp: datetime
