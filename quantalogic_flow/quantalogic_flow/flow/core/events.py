"""
Core events module for workflow system.

This module contains the event system components for workflow execution monitoring.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class WorkflowEventType(Enum):
    """Defines the types of events that can occur during workflow execution."""
    WORKFLOW_STARTED = "WORKFLOW_STARTED"
    WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"
    WORKFLOW_FAILED = "WORKFLOW_FAILED"
    NODE_STARTED = "NODE_STARTED"
    NODE_COMPLETED = "NODE_COMPLETED"
    NODE_FAILED = "NODE_FAILED"
    TRANSITION_EVALUATED = "TRANSITION_EVALUATED"
    SUB_WORKFLOW_ENTERED = "SUB_WORKFLOW_ENTERED"
    SUB_WORKFLOW_EXITED = "SUB_WORKFLOW_EXITED"
    PARALLEL_EXECUTION_STARTED = "PARALLEL_EXECUTION_STARTED"
    PARALLEL_EXECUTION_COMPLETED = "PARALLEL_EXECUTION_COMPLETED"
    PARALLEL_EXECUTION_FAILED = "PARALLEL_EXECUTION_FAILED"


class WorkflowEvent:
    """Represents an event that occurred during workflow execution."""

    def __init__(
        self,
        event_type: WorkflowEventType,
        node_name: Optional[str],
        context: Dict[str, Any],
        result: Optional[Any] = None,
        exception: Optional[Exception] = None,
        transition_from: Optional[str] = None,
        transition_to: Optional[str] = None,
        sub_workflow_name: Optional[str] = None,
        usage: Optional[Dict[str, Any]] = None,
        parallel_nodes: Optional[List[str]] = None,
    ):
        self.event_type = event_type
        self.node_name = node_name
        self.context = context
        self.result = result
        self.exception = exception
        self.transition_from = transition_from
        self.transition_to = transition_to
        self.sub_workflow_name = sub_workflow_name
        self.usage = usage
        self.parallel_nodes = parallel_nodes

    def __repr__(self):
        return f"WorkflowEvent({self.event_type.value}, node={self.node_name}, ...)"


# Type alias for observer functions
WorkflowObserver = Callable[[WorkflowEvent], None]
