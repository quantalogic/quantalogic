"""History management module for storing and formatting agent steps."""

from typing import Dict, List

from loguru import logger
from lxml import etree

from .xml_utils import XMLResultHandler  # Updated import


class HistoryManager:
    """Manages the storage and formatting of agent step history."""
    def __init__(self, max_tokens: int = 16000):
        self.max_tokens: int = max_tokens
        self.store: List[Dict] = []

    def add_step(self, step_data: Dict) -> None:
        """Add a step to the history store."""
        self.store.append(step_data)
        logger.debug(f"Added step {step_data['step_number']} to history")

    def format_history(self, max_iterations: int) -> str:
        """Format the history with available variables, truncating to fit within max_tokens."""
        included_steps: List[str] = []
        total_tokens: int = 0
        for step in reversed(self.store):
            try:
                root = etree.fromstring(step['result'])
                vars_elem = root.find("Variables")
                available_vars = (
                    [var.get('name') for var in vars_elem.findall("Variable")]
                    if vars_elem is not None else []
                )
            except etree.XMLSyntaxError:
                available_vars = []

            step_str: str = (
                f"===== Step {step['step_number']} of {max_iterations} max =====\n"
                f"Thought:\n{step['thought']}\n\n"
                f"Action:\n{step['action']}\n\n"
                f"Result:\n{XMLResultHandler.format_result_summary(step['result'])}\n"
                f"Available variables: {', '.join(available_vars) or 'None'}"
            )
            step_tokens: int = len(step_str.split())
            if total_tokens + step_tokens > self.max_tokens:
                break
            included_steps.append(step_str)
            total_tokens += step_tokens
        return "\n".join(reversed(included_steps)) or "No previous steps"