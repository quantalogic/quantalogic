"""Tool for prompting the user with a question and capturing their input."""

from loguru import logger
from rich.prompt import Prompt

from quantalogic.tools.tool import Tool, ToolArgument


class InputQuestionTool(Tool):
    """Tool to prompt the user with a question and capture their input."""

    name: str = "input_question_tool"
    description: str = "Prompts the user with a question and captures their input."
    arguments: list = [
        ToolArgument(
            name="question",
            arg_type="string",
            description="The question to ask the user.",
            required=True,
            example="What is your favorite color?",
        ),
        ToolArgument(
            name="default",
            arg_type="string",
            description="Optional default value if no input is provided.",
            required=False,
            example="blue",
        ),
    ]

    def execute(self, question: str, default: str | None = None) -> str:
        """Prompts the user with a question and captures their input.

        Args:
            question (str): The question to ask the user.
            default (str | None, optional): Optional default value. Defaults to None.

        Returns:
            str: The user's input or the default value.
        """
        try:
            # Use rich.prompt to create an interactive prompt
            user_input = Prompt.ask(question, default=default)

            # Log the input for debugging purposes
            logger.debug(f"User input for question '{question}': {user_input}")

            return user_input
        except Exception as e:
            # Log any errors that occur during input
            logger.error(f"Error in input_question tool: {e}")
            raise


if __name__ == "__main__":
    tool = InputQuestionTool()
    print(tool.to_markdown())
