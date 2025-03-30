"""Tool management module for defining and retrieving agent tools."""

import asyncio
import importlib
import os
from contextlib import AsyncExitStack
from pathlib import Path
from typing import List, Optional

import litellm
from loguru import logger

from quantalogic.tools import Tool, ToolArgument

from .utils import log_tool_method


class ToolRegistry:
    """Manages tool registration with dependency and conflict checking."""
    def __init__(self):
        self.tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool, checking for conflicts."""
        if tool.name in self.tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        # Placeholder for dependency checking (e.g., required libraries)
        self.tools[tool.name] = tool

    def get_tools(self) -> List[Tool]:
        """Return all registered tools."""
        return list(self.tools.values())


class AgentTool(Tool):
    """Tool for generating text using a language model."""
    def __init__(self, model: str = None, timeout: int = None) -> None:
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
        self.model: str = model or os.getenv("AGENT_MODEL", "gemini/gemini-2.0-flash")
        self.timeout: int = timeout or int(os.getenv("AGENT_TIMEOUT", "30"))

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
    """Tool to retrieve information from a specific previous step with indexed access."""
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
        self.history_index: dict[int, dict] = {i + 1: step for i, step in enumerate(history_store)}

    @log_tool_method
    async def async_execute(self, **kwargs) -> str:
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
    
    registry = ToolRegistry()
    
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

    for tool in static_tools:
        registry.register(tool)

    # Dynamically load tools from the tools/ subdirectory
    tools_dir: Path = Path(__file__).parent / "tools"
    for tool_file in tools_dir.glob("*.py"):
        if tool_file.stem == "__init__":
            continue
        module = importlib.import_module(f".tools.{tool_file.stem}", package="quantalogic.codeact")
        # Iterate over module attributes to find Tool instances
        for name, obj in module.__dict__.items():
            # Only consider objects that are Tool instances with async_execute
            if isinstance(obj, Tool) and hasattr(obj, 'async_execute'):
                try:
                    registry.register(obj)
                    logger.debug(f"Registered tool: {name} from {tool_file.stem}")
                except ValueError as e:
                    logger.warning(f"Failed to register tool {name} in {tool_file.stem}: {e}")
            # Silently skip non-Tool attributes (e.g., __name__, math, etc.)

    combined_tools = registry.get_tools()
    logger.info(f"Loaded {len(combined_tools)} default tools: {[tool.name for tool in combined_tools]}")
    return combined_tools