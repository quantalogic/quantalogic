from datetime import datetime
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