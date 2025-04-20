"""RetrieveStepTool definition for Quantalogic CodeAct framework."""

from typing import Any, Dict, List, Optional

from loguru import logger

from quantalogic.tools import Tool, ToolArgument

from ..utils import log_tool_method


class RetrieveStepTool(Tool):
    """Tool to retrieve information from a specific previous step with indexed access."""
    def __init__(self, history_store: List[dict], config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the RetrieveStepTool with history store."""
        try:
            super().__init__(
                name="retrieve_step",
                description="Retrieve the thought, action, and result from a specific step.",
                arguments=[
                    ToolArgument(name="step_number", arg_type="int", description="The step number to retrieve (1-based)", required=True)
                ],
                return_type="string"
            )
            self.config = config or {}
            self.history_index: Dict[int, dict] = {i + 1: step for i, step in enumerate(history_store)}
        except Exception as e:
            logger.error(f"Failed to initialize RetrieveStepTool: {e}")
            raise

    @log_tool_method
    async def async_execute(self, **kwargs) -> str:
        """Execute the tool to retrieve step information."""
        try:
            step_number: int = kwargs["step_number"]
            if step_number not in self.history_index:
                error_msg = f"Error: Step {step_number} is out of range (1-{len(self.history_index)})"
                logger.error(error_msg)
                raise ValueError(error_msg)
            step: dict = self.history_index[step_number]
            result = (
                f"Step {step_number}:\n"
                f"Thought: {step['thought']}\n"
                f"Action: {step['action']}\n"
                f"Result: {step['result']}"
            )
            logger.info(f"Retrieved step {step_number} successfully")
            return result
        except Exception as e:
            logger.error(f"Error retrieving step {kwargs.get('step_number', 'unknown')}: {e}")
            return f"Error: {str(e)}"
