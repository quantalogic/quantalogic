from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class Event(BaseModel):
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.now)

class ExecutionResult(BaseModel):
    execution_status: str  # 'success' or 'error'
    error: Optional[str] = None
    execution_time: Optional[float] = None
    task_status: Optional[str] = None  # 'completed' or 'inprogress'
    result: Optional[str] = None
    next_step: Optional[str] = None
    local_variables: Optional[Dict[str, Any]] = None

    def to_summary(self) -> str:
        """Generate a formatted summary of the execution result."""
        lines = [f"- Execution Status: {self.execution_status}"]
        if self.execution_status == 'success':
            lines.append(f"- Task Status: {self.task_status or 'N/A'}")
            lines.append(f"- Result: {self.result or 'N/A'}")
            if self.next_step:
                lines.append(f"- Next Step: {self.next_step}")
        else:
            lines.append(f"- Error: {self.error or 'N/A'}")
        lines.append(f"- Execution Time: {self.execution_time:.2f} seconds")
        if self.local_variables:
            lines.append("- Variables:")
            for k, v in self.local_variables.items():
                var_str = str(v)[:500] + ("..." if len(str(v)) > 500 else "")
                lines.append(f"  - {k}: {var_str}")
        return "\n".join(lines)

class TaskStartedEvent(Event):
    task_description: str
    system_prompt: str = ""  # Added for persistent context

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
    result: ExecutionResult
    execution_time: float

class StepCompletedEvent(Event):
    step_number: int
    thought: str
    action: str
    result: Dict[str, Any]  # Changed to dict to match ExecutionResult.dict()
    is_complete: bool
    final_answer: Optional[str] = None

class ErrorOccurredEvent(Event):
    error_message: str
    step_number: Optional[int] = None

class TaskCompletedEvent(Event):
    final_answer: Optional[str]
    reason: str

class StepStartedEvent(Event):
    step_number: int
    system_prompt: str = ""  # Added for persistent context
    task_description: str = ""  # Added for persistent context

class ToolExecutionStartedEvent(Event):
    step_number: int
    tool_name: str
    parameters_summary: Dict[str, Any]

class ToolExecutionCompletedEvent(Event):
    step_number: int
    tool_name: str
    result_summary: str

class ToolExecutionErrorEvent(Event):
    step_number: int
    tool_name: str
    error: str

class StreamTokenEvent(Event):
    token: str
    step_number: Optional[int] = None

class PromptGeneratedEvent(Event):
    step_number: int
    prompt: str