from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Event(BaseModel):
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.now)


class TaskStartedEvent(Event):
    task_description: str


class ThoughtGeneratedEvent(Event):
    step_number: int
    thought: str
    generation_time: float


class ActionGeneratedEvent(Event):
    step_number: int
    action_code: str
    generation_time: float


class ActionExecutedEvent(Event):
    step_number: int
    result_xml: str
    execution_time: float


class StepCompletedEvent(Event):
    step_number: int
    thought: str
    action: str
    result: str
    is_complete: bool
    final_answer: str | None = None


class ErrorOccurredEvent(Event):
    error_message: str
    step_number: int | None = None


class TaskCompletedEvent(Event):
    final_answer: str | None
    reason: str


class StepStartedEvent(Event):
    step_number: int


class ToolExecutionStartedEvent(Event):
    step_number: int
    tool_name: str
    parameters_summary: dict  # Summary of tool parameters (e.g., {"param1": "value1"})


class ToolExecutionCompletedEvent(Event):
    step_number: int
    tool_name: str
    result_summary: str  # Summary of the execution result


class ToolExecutionErrorEvent(Event):
    step_number: int
    tool_name: str
    error: str  # Error message if execution fails


# In quantalogic/codeact/events.py
class StreamTokenEvent(Event):
    token: str
    step_number: Optional[int] = None