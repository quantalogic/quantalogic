"""Web Navigation Tool using browser-use for automated web interactions."""

import asyncio
from typing import Callable, Optional

from loguru import logger
from pydantic import ConfigDict, Field

from browser_use import Agent
from langchain_openai import ChatOpenAI
from quantalogic.tools.tool import Tool, ToolArgument


class WebNavigationTool(Tool):
    """Tool for automated web navigation and interaction using browser-use."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    name: str = Field(default="web_navigation")
    description: str = Field(
        default=(
            "Navigate and interact with web pages using natural language instructions. "
            "This tool can perform tasks like searching, comparing prices, filling forms, "
            "and extracting information from websites."
        )
    )
    arguments: list = Field(
        default=[
            ToolArgument(
                name="task",
                arg_type="string",
                description="The web navigation task to perform in natural language",
                required=True,
                example="Search Python documentation for asyncio examples",
            ),
            ToolArgument(
                name="model_name",
                arg_type="string",
                description="The OpenAI model to use (e.g. gpt-3.5-turbo, gpt-4)",
                required=True,
                default="gpt-3.5-turbo",
                example="gpt-3.5-turbo",
            ),
        ]
    )

    llm: Optional[ChatOpenAI] = Field(default=None, exclude=True)
    agent: Optional[Agent] = Field(default=None, exclude=True)

    def __init__(
        self,
        model_name: str = "gpt-3.5-turbo",
        name: str = "web_navigation",
    ) -> None:
        """Initialize the WebNavigationTool.

        Args:
            model_name: OpenAI model to use. Defaults to "gpt-3.5-turbo".
            name: Name of the tool instance. Defaults to "web_navigation".
        """
        super().__init__(
            **{
                "name": name,
                "model_name": model_name,
            }
        )
        self.model_post_init(None)

    def model_post_init(self, __context: None) -> None:
        """Initialize the LLM after model initialization.
        
        Args:
            __context: Unused context parameter.
        
        Raises:
            ValueError: If LLM initialization fails.
        """
        try:
            self.llm = ChatOpenAI(model=self.model_name)
            logger.debug(f"Initialized WebNavigationTool with model: {self.model_name}")
        except Exception as e:
            logger.error(f"Error initializing LLM: {e}")
            raise ValueError(f"Failed to initialize LLM: {e}") from e

    async def async_execute(self, task: str, model_name: Optional[str] = None) -> str:
        """Execute the web navigation task asynchronously.

        Args:
            task: The web navigation task to perform.
            model_name: Optional override for the LLM model.

        Returns:
            The result of the web navigation task.

        Raises:
            ValueError: If task is empty or LLM is not initialized.
            RuntimeError: If web navigation fails.
        """
        if not task:
            raise ValueError("Task cannot be empty")
            
        if not self.llm:
            raise ValueError("LLM not initialized")

        try:
            # Create a new Agent instance for each task
            agent = Agent(
                task=task,
                llm=self.llm,
            )
            
            # Run the agent
            result = await agent.run()
            logger.debug(f"Completed web navigation task: {task}")
            return result

        except Exception as e:
            logger.error(f"Error during web navigation: {e}")
            raise RuntimeError(f"Web navigation failed: {e}") from e

    def execute(self, task: str, model_name: Optional[str] = None) -> str:
        """Execute the web navigation task synchronously.

        Args:
            task: The web navigation task to perform.
            model_name: Optional override for the LLM model.

        Returns:
            The result of the web navigation task.
        """
        return asyncio.run(self.async_execute(task=task, model_name=model_name))


if __name__ == "__main__":
    # Example usage
    tool = WebNavigationTool()
    task = "Search Python documentation for asyncio examples"
    
    try:
        # Synchronous execution
        result = tool.execute(task=task)
        print("Navigation Result:")
        print(result)
    except Exception as e:
        logger.error(f"Example failed: {e}")
