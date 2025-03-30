"""Tool for reading a file and returning its content."""

from loguru import logger
from quantalogic.tools.tool import Tool, ToolArgument


class TaskCompleteTool(Tool):
    """Tool to reply answer to the user."""

    name: str = "task_complete"
    description: str = "Replies to the user when the task is completed."
    arguments: list = [
        ToolArgument(
            name="answer",
            arg_type="string",
            description="The answer to the user. Use interpolation if possible example $var1$.",
            required=True,
            example="The answer to the meaning of life",
        ),
    ]

    def execute(self, answer: str) -> str:
        """Attempts to reply to the user.

        Args:
            answer (str): The answer to the user.

        Returns:
            str: The answer to the user.

        Raises:
            ValueError: If the answer contains uninterpolated variables.
        """
        import re

        # Check for any variable-like patterns
        var_pattern = r'\$[a-zA-Z_][a-zA-Z0-9_]*\$?'
        matches = re.findall(var_pattern, answer)
        
        if matches:
            var_list = ", ".join(matches)
            error_msg = (
                f"Error: Task complete answer contains uninterpolated variables: {var_list}. "
                "Variables should be interpolated before completing the task."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        return answer


if __name__ == "__main__":
    tool = TaskCompleteTool()
    print(tool.to_markdown())
