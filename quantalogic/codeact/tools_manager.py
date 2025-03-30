"""Tool management module for defining and retrieving agent tools."""

import asyncio
import importlib
from contextlib import AsyncExitStack
from pathlib import Path
from typing import List, Optional

import litellm
from loguru import logger

from quantalogic.tools import Tool, ToolArgument

from .utils import log_tool_method


class AgentTool(Tool):
    """Tool for generating text using a language model."""
    def __init__(self, model: str = "gemini/gemini-2.0-flash", timeout: int = 30) -> None:
        super().__init__(
            name="agent_tool",
            description="Generates text using a language model.",
            arguments=[
                ToolArgument(name="system_prompt", arg_type="string", 
                            description="System prompt to guide the model", required=True),
                ToolArgument(name="prompt", arg_type="string", 
                            description="User prompt to generate a response", required=True),
                ToolArgument(name="temperature", arg_type="float", 
                            description="Temperature for generation (0 to 1)", required=True)
            ],
            return_type="string"
        )
        self.model: str = model
        self.timeout: int = timeout

    @log_tool_method
    async def async_execute(self, **kwargs) -> str:
        system_prompt: str = kwargs["system_prompt"]
        prompt: str = kwargs["prompt"]
        temperature: float = float(kwargs["temperature"])

        if not 0 <= temperature <= 1:
            raise ValueError("Temperature must be between 0 and 1")

        logger.info(f"Generating with {self.model}, temp={temperature}, timeout={self.timeout}s")
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(asyncio.timeout(self.timeout))
            try:
                response = await litellm.acompletion(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=temperature,
                    max_tokens=1000
                )
                result = response.choices[0].message.content.strip()
                logger.info(f"AgentTool generated text successfully: {result[:50]}...")
                return result
            except Exception as e:
                error_msg = f"Error: Unable to generate text due to {str(e)}"
                logger.error(f"AgentTool failed: {e}")
                return error_msg


class RetrieveStepTool(Tool):
    """Tool to retrieve information from a specific previous step."""
    def __init__(self, history_store: List[dict]) -> None:
        super().__init__(
            name="retrieve_step",
            description="Retrieve the thought, action, and result from a specific step.",
            arguments=[
                ToolArgument(name="step_number", arg_type="int", 
                            description="The step number to retrieve (1-based)", required=True)
            ],
            return_type="string"
        )
        self.history_store: List[dict] = history_store

    @log_tool_method
    async def async_execute(self, **kwargs) -> str:
        step_number: int = kwargs["step_number"]
        if not (1 <= step_number <= len(self.history_store)):
            error_msg = f"Error: Step {step_number} is out of range (1-{len(self.history_store)})"
            logger.error(error_msg)
            raise ValueError(error_msg)
        step: dict = self.history_store[step_number - 1]
        result = (
            f"Step {step_number}:\n"
            f"Thought: {step['thought']}\n"
            f"Action: {step['action']}\n"
            f"Result: {step['result']}"
        )
        logger.info(f"Retrieved step {step_number} successfully")
        return result


def get_default_tools(model: str, history_store: Optional[List[dict]] = None) -> List[Tool]:
    """Dynamically load default tools from the tools/ directory.

    Args:
        model (str): The language model to use for model-specific tools.
        history_store (Optional[List[dict]]): Optional history store for RetrieveStepTool.

    Returns:
        List[Tool]: A list of initialized tool instances.
    """
    from quantalogic.tools import (
        GrepAppTool,
        InputQuestionTool,
        ListDirectoryTool,
        ReadFileBlockTool,
        ReadFileTool,
        ReadHTMLTool,
        WriteFileTool,
    )
    
    # Core tools that don't need dynamic loading
    static_tools: List[Tool] = [
        GrepAppTool(),
        InputQuestionTool(),
        ListDirectoryTool(),
        ReadFileBlockTool(),
        ReadFileTool(),
        ReadHTMLTool(),
        WriteFileTool(disable_ensure_tmp_path=True),
        AgentTool(model=model)
    ]
    if history_store is not None:
        static_tools.append(RetrieveStepTool(history_store))

    # Dynamically load tools from the tools/ subdirectory
    tools_dir: Path = Path(__file__).parent / "tools"
    dynamic_tools: List[Tool] = []
    for tool_file in tools_dir.glob("*.py"):
        if tool_file.stem == "__init__":
            continue
        module = importlib.import_module(f".tools.{tool_file.stem}", package="quantalogic.codeact")
        for name, obj in module.__dict__.items():
            if isinstance(obj, Tool) and hasattr(obj, 'async_execute'):
                dynamic_tools.append(obj)
            else:
                logger.warning(f"Skipping invalid tool in {tool_file.stem}: {name} - not a valid Tool instance")

    combined_tools = static_tools + dynamic_tools
    logger.info(f"Loaded {len(combined_tools)} default tools: {[tool.name for tool in combined_tools]}")
    return combined_tools