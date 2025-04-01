"""Tool management module for defining and retrieving agent tools."""

import asyncio
import importlib
import importlib.metadata
import inspect
import os
from contextlib import AsyncExitStack
from typing import List, Optional

import litellm
from loguru import logger

from quantalogic.tools import Tool, ToolArgument

from .utils import log_tool_method


class ToolRegistry:
    """Manages tool registration with dependency and conflict checking."""
    def __init__(self):
        # Use tuple (toolbox_name, tool_name) as key to allow same names across toolboxes
        self.tools: dict[tuple[str, str], Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool, checking for conflicts within the same toolbox."""
        key = (tool.toolbox_name or "default", tool.name)
        if key in self.tools:
            raise ValueError(f"Tool '{tool.name}' in toolbox '{tool.toolbox_name or 'default'}' is already registered")
        self.tools[key] = tool
        logger.debug(f"Tool registered: {tool.name} in toolbox {tool.toolbox_name or 'default'}")

    def get_tools(self) -> List[Tool]:
        """Return all registered tools."""
        logger.debug(f"Returning {len(self.tools)} tools: {list(self.tools.keys())}")
        return list(self.tools.values())

    def register_tools_from_module(self, module, toolbox_name: str) -> None:
        """Register all @create_tool generated Tool instances from a module with toolbox name."""
        tools_found = False
        for name, obj in inspect.getmembers(module):
            if isinstance(obj, Tool) and hasattr(obj, '_func'):
                obj.toolbox_name = toolbox_name
                self.register(obj)
                logger.debug(f"Registered tool: {obj.name} from {module.__name__} in toolbox {toolbox_name}")
                tools_found = True
        if not tools_found:
            logger.warning(f"No @create_tool generated tools found in {module.__name__}")

    def load_toolboxes(self, toolbox_names: Optional[List[str]] = None) -> None:
        """Load toolboxes from registered entry points, optionally filtering by name."""
        try:
            entry_points = importlib.metadata.entry_points(group="quantalogic.tools")
        except Exception as e:
            logger.error(f"Failed to retrieve entry points: {e}")
            entry_points = []

        if toolbox_names is not None:
            entry_points = [ep for ep in entry_points if ep.name in toolbox_names]

        logger.debug(f"Found {len(entry_points)} toolbox entry points")
        for ep in entry_points:
            try:
                module = ep.load()
                self.register_tools_from_module(module, toolbox_name=ep.name)
                logger.info(f"Successfully loaded toolbox: {ep.name}")
            except ImportError as e:
                logger.error(f"Failed to import toolbox {ep.name}: {e}")


class AgentTool(Tool):
    """A specialized tool for generating text using language models, designed for AI agent workflows."""
    def __init__(self, model: str = None, timeout: int = None) -> None:
        super().__init__(
            name="agent_tool",
            description="Generates text using a language model. This is a stateless agent - all necessary context must be explicitly provided in either the system prompt or user prompt.",
            arguments=[
                ToolArgument(name="system_prompt", arg_type="string", description="System prompt to guide the model", required=True),
                ToolArgument(name="prompt", arg_type="string", description="User prompt to generate a response", required=True),
                ToolArgument(name="temperature", arg_type="float", description="Temperature for generation (0 to 1)", required=True)
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
                ToolArgument(name="step_number", arg_type="int", description="The step number to retrieve (1-based)", required=True)
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


def get_default_tools(
    model: str,
    history_store: Optional[List[dict]] = None,
    enabled_toolboxes: Optional[List[str]] = None
) -> List[Tool]:
    """Dynamically load default tools and toolboxes via entry points."""
    registry = ToolRegistry()
    
    static_tools: List[Tool] = [AgentTool(model=model)]
    if history_store is not None:
        static_tools.append(RetrieveStepTool(history_store))

    for tool in static_tools:
        registry.register(tool)

    registry.load_toolboxes(toolbox_names=enabled_toolboxes)
    combined_tools = registry.get_tools()
    logger.info(f"Loaded {len(combined_tools)} default tools: {[(tool.toolbox_name or 'default', tool.name) for tool in combined_tools]}")
    return combined_tools