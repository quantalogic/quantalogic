"""Tool management module for defining and retrieving agent tools."""

import asyncio
import importlib
import importlib.metadata
import inspect
import os
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

import litellm
from loguru import logger

from quantalogic.tools import Tool, ToolArgument, create_tool

from .utils import log_tool_method


class ToolRegistry:
    """Manages tool registration with dependency and conflict checking."""
    def __init__(self):
        self.tools: Dict[tuple[str, str], Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool, checking for conflicts within the same toolbox."""
        try:
            key = (tool.toolbox_name or "default", tool.name)
            if key in self.tools:
                logger.warning(f"Tool '{tool.name}' in toolbox '{tool.toolbox_name or 'default'}' is already registered. Skipping.")
                return
            self.tools[key] = tool
            logger.debug(f"Tool registered: {tool.name} in toolbox {tool.toolbox_name or 'default'}")
        except Exception as e:
            logger.error(f"Failed to register tool {tool.name}: {e}")
            raise

    def get_tools(self) -> List[Tool]:
        """Return all registered tools."""
        try:
            logger.debug(f"Returning {len(self.tools)} tools: {list(self.tools.keys())}")
            return list(self.tools.values())
        except Exception as e:
            logger.error(f"Error retrieving tools: {e}")
            return []

    def register_tools_from_module(self, module, toolbox_name: str) -> None:
        """Register tools from a module, supporting both @create_tool, get_tools, and DynamicTool approaches."""
        try:
            tools_found = False
            logger.debug(f"Processing module {getattr(module, '__name__', str(module))} for toolbox {toolbox_name}")
            # Check for get_tools function to register dependency-free tools
            if hasattr(module, 'get_tools'):
                tool_funcs = module.get_tools()
                for func in tool_funcs:
                    # Ensure function is async
                    if not inspect.iscoroutinefunction(func):
                        logger.warning(f"Function '{getattr(func, '__name__', str(func))}' in {getattr(module, '__name__', str(module))} is not async. Skipping.")
                        continue
                    tool = create_tool(func)
                    tool.toolbox_name = toolbox_name
                    self.register(tool)
                    logger.debug(f"Registered tool from get_tools: {tool.name} in toolbox {toolbox_name}")
                    tools_found = True

            # Register @create_tool-decorated Tool instances
            for name, obj in inspect.getmembers(module):
                if isinstance(obj, Tool) and hasattr(obj, '_func'):
                    obj.toolbox_name = toolbox_name
                    self.register(obj)
                    logger.debug(f"Registered @create_tool tool: {obj.name} from {getattr(module, '__name__', str(module))} in toolbox {toolbox_name}")
                    tools_found = True
                # Handle DynamicTool instances (e.g., from MCP)
                elif hasattr(obj, 'name') and hasattr(obj, 'description') and hasattr(obj, 'inputSchema'):
                    try:
                        # Create a Tool instance from DynamicTool
                        arguments = [
                            ToolArgument(
                                name=prop_name,
                                arg_type=prop.get('type', 'string'),
                                description=prop.get('description', ''),
                                required=prop_name in obj.inputSchema.get('required', [])
                            )
                            for prop_name, prop in obj.inputSchema.get('properties', {}).items()
                        ]
                        tool = Tool(
                            name=obj.name,
                            description=obj.description + "\nNote: This tool is asynchronous and must be awaited using `await` in an async context.",
                            arguments=arguments,
                            return_type="Any"
                        )
                        tool.toolbox_name = toolbox_name
                        self.register(tool)
                        logger.debug(f"Registered DynamicTool: {tool.name} in toolbox {toolbox_name}")
                        tools_found = True
                    except Exception as e:
                        logger.warning(f"Failed to register DynamicTool '{getattr(obj, 'name', 'unknown')}' in {toolbox_name}: {e}")
                        continue

            if not tools_found:
                logger.warning(f"No tools found in {getattr(module, '__name__', str(module))}")
        except Exception as e:
            logger.error(f"Failed to register tools from module {getattr(module, '__name__', str(module))}: {e}")
            # Continue without raising to allow other toolboxes to load
            return

    def load_toolboxes(self, toolbox_names: Optional[List[str]] = None) -> None:
        """Load toolboxes from registered entry points, optionally filtering by name."""
        try:
            entry_points = importlib.metadata.entry_points(group="quantalogic.tools")
        except Exception as e:
            logger.error(f"Failed to retrieve entry points: {e}")
            entry_points = []

        try:
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
                except Exception as e:
                    logger.error(f"Failed to load toolbox {ep.name}: {e}")
        except Exception as e:
            logger.error(f"Error loading toolboxes: {e}")


class AgentTool(Tool):
    """A specialized tool for generating text using language models, designed for AI agent workflows."""
    def __init__(self, model: str = None, timeout: int = None, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the AgentTool with configurable model and timeout."""
        try:
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
            self.config = config or {}
            self.model: str = self._resolve_model(model)
            self.timeout: int = self._resolve_timeout(timeout)
        except Exception as e:
            logger.error(f"Failed to initialize AgentTool: {e}")
            raise

    def _resolve_model(self, model: Optional[str]) -> str:
        """Resolve the model from config, argument, or environment variable."""
        try:
            return self.config.get("model", model) or os.getenv("AGENT_MODEL", "gemini/gemini-2.0-flash")
        except Exception as e:
            logger.error(f"Error resolving model: {e}. Using default.")
            return "gemini/gemini-2.0-flash"

    def _resolve_timeout(self, timeout: Optional[int]) -> int:
        """Resolve the timeout from config, argument, or environment variable."""
        try:
            return self.config.get("timeout", timeout) or int(os.getenv("AGENT_TIMEOUT", "30"))
        except (ValueError, TypeError) as e:
            logger.error(f"Error resolving timeout: {e}. Using default.")
            return 30

    @log_tool_method
    async def async_execute(self, **kwargs) -> str:
        """Execute the tool asynchronously with error handling."""
        try:
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
        except TimeoutError:
            logger.error(f"AgentTool execution timed out after {self.timeout}s")
            return "Error: Execution timed out"
        except Exception as e:
            logger.error(f"Unexpected error in AgentTool execution: {e}")
            return f"Error: {str(e)}"


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


def get_default_tools(
    model: str,
    history_store: Optional[List[dict]] = None,
    enabled_toolboxes: Optional[List[str]] = None,
    tools_config: Optional[List[Dict[str, Any]]] = None
) -> List[Tool]:
    """Dynamically load default tools using the pre-loaded registry from PluginManager."""
    from .cli import plugin_manager

    try:
        plugin_manager.load_plugins()
        registry = plugin_manager.tools
        
        static_tools: List[Tool] = [AgentTool(model=model)]
        if history_store is not None:
            static_tools.append(RetrieveStepTool(history_store))

        for tool in static_tools:
            try:
                registry.register(tool)
            except ValueError as e:
                logger.debug(f"Static tool {tool.name} already registered: {e}")

        if enabled_toolboxes:
            tools = [t for t in registry.get_tools() if t.toolbox_name in enabled_toolboxes]
        else:
            tools = registry.get_tools()

        if tools_config:
            filtered_tools = []
            processed_names = set()
            for tool_conf in tools_config:
                if tool_conf.get("enabled", True):
                    tool = next((t for t in tools if t.name == tool_conf["name"] or t.toolbox_name == tool_conf["name"]), None)
                    if tool and tool.name not in processed_names:
                        for key, value in tool_conf.items():
                            if key not in ["name", "enabled"]:
                                setattr(tool, key, value)
                        filtered_tools.append(tool)
                        processed_names.add(tool.name)
            for tool in tools:
                if tool.name not in processed_names:
                    filtered_tools.append(tool)
            tools = filtered_tools
        
        logger.info(f"Loaded {len(tools)} default tools: {[(tool.toolbox_name or 'default', tool.name) for tool in tools]}")
        return tools
    except Exception as e:
        logger.error(f"Failed to load default tools: {e}")
        return []