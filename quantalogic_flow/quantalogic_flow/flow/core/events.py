"""
Core events module for workflow system.

This module contains the event system components for workflow execution monitoring.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional


class WorkflowEventType(Enum):
    """Event types that can occur during workflow execution."""
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    TRANSITION_EVALUATED = "transition_evaluated"
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    SUB_WORKFLOW_ENTERED = "sub_workflow_entered"
    SUB_WORKFLOW_EXITED = "sub_workflow_exited"


@dataclass
class WorkflowEvent:
    """Event data structure for workflow execution events."""
    event_type: WorkflowEventType
    node_name: Optional[str]
    context: Dict[str, Any]
    result: Optional[Any] = None
    exception: Optional[Exception] = None
    transition_from: Optional[str] = None
    transition_to: Optional[str] = None
    sub_workflow_name: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None


# Type alias for observer functions
WorkflowObserver = Callable[[WorkflowEvent], None]
