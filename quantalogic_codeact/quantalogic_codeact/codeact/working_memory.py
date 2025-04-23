from dataclasses import dataclass
from typing import Dict, List

from loguru import logger

from .events import ExecutionResult
from .templates import jinja_env


@dataclass
class Step:
    step_number: int
    thought: str
    action: str
    result: ExecutionResult


class WorkingMemory:
    """Manages the storage and formatting of agent step history with persistent context."""
    
    def __init__(self, max_tokens: int = 64*1024, system_prompt: str = "", task_description: str = ""):
        """
        Initialize the WorkingMemory with a token limit and persistent context.

        Args:
            max_tokens (int): Maximum number of tokens for history formatting (default: 65536).
            system_prompt (str): Persistent system-level instructions for the agent (default: "").
            task_description (str): Persistent description of the current task (default: "").
        """
        self.max_tokens: int = max_tokens
        self._system_prompt: str = system_prompt
        self._task_description: str = task_description
        self._store: List[Step] = []
        logger.debug(f"Initialized WorkingMemory with system_prompt: '{system_prompt}', task_description: '{task_description}'")

    @property
    def system_prompt(self) -> str:
        """Get the system prompt."""
        return self._system_prompt

    @system_prompt.setter
    def system_prompt(self, value: str) -> None:
        """Set the system prompt."""
        self._system_prompt = value

    @property
    def task_description(self) -> str:
        """Get the task description."""
        return self._task_description

    @task_description.setter
    def task_description(self, value: str) -> None:
        """Set the task description."""
        self._task_description = value

    @property
    def store(self) -> List[Step]:
        """Get the step store."""
        return self._store

    def add(self, step_data: Dict) -> None:
        """
        Add a step to the working memory store.

        Args:
            step_data (Dict): Dictionary containing step details (step_number, thought, action, result).
        """
        try:
            step = Step(
                step_number=step_data['step_number'],
                thought=step_data['thought'],
                action=step_data['action'],
                result=ExecutionResult(**step_data['result'])
            )
            self._store.append(step)
            logger.debug(f"Added step {step.step_number} to working memory")
        except Exception as e:
            logger.error(f"Failed to add step: {e}")

    def clear(self) -> None:
        """Clear the task history for a new task."""
        try:
            self._store = []
            logger.debug("Cleared task history")
        except Exception as e:
            logger.error(f"Error clearing task history: {e}")

    def format_history(self, max_iterations: int) -> str:
        """
        Format the history using a Jinja2 template, truncating to fit within max_tokens.

        Args:
            max_iterations (int): Maximum allowed iterations for context.

        Returns:
            str: Formatted string of previous steps, or "No previous steps" if empty.
        """
        try:
            included_steps: List[str] = []
            total_tokens: int = 0
            step_template = jinja_env.get_template("step.j2")
            for step in reversed(self._store):
                step_str = step_template.render(step=step, max_iterations=max_iterations)
                step_tokens: int = len(step_str.split())
                if total_tokens + step_tokens > self.max_tokens:
                    break
                included_steps.append(step_str)
                total_tokens += step_tokens
            return "\n".join(reversed(included_steps)) or "No previous steps"
        except Exception as e:
            logger.error(f"Error formatting history: {e}")
            return "No previous steps"

    def get_full_context(self, max_iterations: int) -> str:
        """
        Return the full context including system prompt, task description, and formatted history.

        Args:
            max_iterations (int): Maximum allowed iterations for history formatting.

        Returns:
            str: Combined string of system prompt, task description, and history.
        """
        try:
            context_parts = []
            if self._system_prompt:
                context_parts.append(f"System Prompt:\n{self._system_prompt}")
            if self._task_description:
                context_parts.append(f"Task Description:\n{self._task_description}")
            history_str = self.format_history(max_iterations)
            if history_str != "No previous steps":
                context_parts.append(f"History:\n{history_str}")
            return "\n\n".join(context_parts)
        except Exception as e:
            logger.error(f"Error getting full context: {e}")
            return ""