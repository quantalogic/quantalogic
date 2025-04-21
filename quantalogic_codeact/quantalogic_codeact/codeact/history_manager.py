"""History management module for storing and formatting agent steps."""

from typing import Dict, List

from loguru import logger


class HistoryManager:
    """Manages the storage and formatting of agent step history with persistent context."""
    
    def __init__(self, max_tokens: int = 64*1024, system_prompt: str = "", task_description: str = ""):
        """
        Initialize the HistoryManager with a token limit and persistent context.

        Args:
            max_tokens (int): Maximum number of tokens for history formatting (default: 65536).
            system_prompt (str): Persistent system-level instructions for the agent (default: "").
            task_description (str): Persistent description of the current task (default: "").
        """
        self.max_tokens: int = max_tokens
        self.system_prompt: str = system_prompt
        self.task_description: str = task_description
        self.store: List[Dict] = []
        logger.debug(f"Initialized HistoryManager with system_prompt: '{system_prompt}', task_description: '{task_description}'")

    def add(self, step_data: Dict) -> None:
        """
        Add a step to the history store.

        Args:
            step_data (Dict): Dictionary containing step details (step_number, thought, action, result).
        """
        try:
            self.store.append(step_data)
            logger.debug(f"Added step {step_data['step_number']} to history")
        except Exception as e:
            logger.error(f"Failed to add step: {e}")

    def clear(self) -> None:
        """Clear the task history for a new task."""
        try:
            self.store = []
            logger.debug("Cleared task history")
        except Exception as e:
            logger.error(f"Error clearing task history: {e}")

    def format_history(self, max_iterations: int) -> str:
        """
        Format the history with available variables, truncating to fit within max_tokens.

        Args:
            max_iterations (int): Maximum allowed iterations for context.

        Returns:
            str: Formatted string of previous steps, or "No previous steps" if empty.
        """
        try:
            included_steps: List[str] = []
            total_tokens: int = 0
            for step in reversed(self.store):
                result_dict = step['result']
                # Format result summary
                summary_lines = [f"- Execution Status: {result_dict['execution_status']}"]
                if result_dict['execution_status'] == 'success':
                    summary_lines.append(f"- Task Status: {result_dict.get('task_status', 'N/A')}")
                    summary_lines.append(f"- Result: {result_dict.get('result', 'N/A')}")
                    if result_dict.get('next_step'):
                        summary_lines.append(f"- Next Step: {result_dict['next_step']}")
                else:
                    summary_lines.append(f"- Error: {result_dict.get('error', 'N/A')}")
                summary_lines.append(f"- Execution Time: {result_dict.get('execution_time', 0.0):.2f} seconds")
                if result_dict.get('local_variables'):
                    summary_lines.append("- Variables:")
                    for k, v in result_dict['local_variables'].items():
                        var_str = str(v)[:500] + ("..." if len(str(v)) > 500 else "")
                        summary_lines.append(f"  - {k}: {var_str}")
                result_summary = "\n".join(summary_lines)

                step_str = (
                    f"===== Step {step['step_number']} of {max_iterations} max =====\n"
                    f"Thought:\n{step['thought']}\n\n"
                    f"Action:\n{step['action']}\n\n"
                    f"Result:\n{result_summary}"
                )
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
            if self.system_prompt:
                context_parts.append(f"System Prompt:\n{self.system_prompt}")
            if self.task_description:
                context_parts.append(f"Task Description:\n{self.task_description}")
            history_str = self.format_history(max_iterations)
            if history_str != "No previous steps":
                context_parts.append(f"History:\n{history_str}")
            return "\n\n".join(context_parts)
        except Exception as e:
            logger.error(f"Error getting full context: {e}")
            return ""