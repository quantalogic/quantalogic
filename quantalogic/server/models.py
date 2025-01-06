"""Pydantic models for the QuantaLogic API."""

from typing import Any, Dict, Optional

from pydantic import BaseModel

from quantalogic.agent_config import MODEL_NAME


class EventMessage(BaseModel):
    """Event message model for SSE."""

    id: str
    event: str
    task_id: Optional[str] = None
    data: Dict[str, Any]
    timestamp: str

    model_config = {"extra": "forbid"}


class UserValidationRequest(BaseModel):
    """Request model for user validation."""

    question: str
    validation_id: str | None = None

    model_config = {"extra": "forbid"}


class UserValidationResponse(BaseModel):
    """Response model for user validation."""

    response: bool

    model_config = {"extra": "forbid"}


class TaskSubmission(BaseModel):
    """Request model for task submission."""

    task: str
    model_name: Optional[str] = MODEL_NAME
    max_iterations: Optional[int] = 30

    model_config = {"extra": "forbid"}


class TaskStatus(BaseModel):
    """Task status response model."""

    task_id: str
    status: str  # "pending", "running", "completed", "failed"
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    total_tokens: Optional[int] = None
    model_name: Optional[str] = None
