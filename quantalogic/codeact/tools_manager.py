"""Tool management module for defining and retrieving agent tools."""

import asyncio
import importlib
import os
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Dict, List, Optional

import litellm
import yaml
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


def load_toolbox(module_name: str) -> List[Tool]:
    """Dynamically load a toolbox module and return its tools."""
    try:
        module = importlib.import_module(module_name)
        if not hasattr(module, 'tools'):
            logger.warning(f"Module {module_name} lacks 'tools' list. Skipping.")
            return []
        return module.tools
    except ImportError as e:
        logger.error(f"Failed to load toolbox {module_name}: {e}")
        return []


def get_toolboxes(model: str, history_store: Optional[List[dict]] = None) -> Dict[str, List[Tool]]:
    """Returns a dictionary of toolboxes with their respective tools, dynamically loaded or static."""
    from quantalogic.tools import (
        GrepAppTool,
        InputQuestionTool,
        ListDirectoryTool,
        ReadFileBlockTool,
        ReadFileTool,
        ReadHTMLTool,
        WriteFileTool,
    )

    toolboxes = {}
    config_path = Path(__file__).parent / "config.yaml"
    loaded_tool_names = set()

    # Try loading from config file first
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
        for tb in config.get('toolboxes', []):
            module_name = tb['module']
            tools = load_toolbox(module_name)
            if tools:
                toolbox_name = tb.get('name', module_name.split('.')[-1])
                toolboxes[toolbox_name] = tools
                loaded_tool_names.update(tool.name for tool in tools)
    except FileNotFoundError:
        # Fallback to original static toolboxes
        logger.info("No config.yaml found, using default static toolboxes.")
        from .tools.concat_tool import concat_tool
        from .tools.cosinus import cosinus
        from .tools.multiply_tool import multiply_tool
        from .tools.sinus import sinus
        toolboxes = {
            "MathToolBox": [sinus, cosinus, multiply_tool],
            "StringToolBox": [concat_tool],
            "FileSystemToolBox": [
                ListDirectoryTool(),
                ReadFileTool(),
                WriteFileTool(disable_ensure_tmp_path=True),
                ReadFileBlockTool(),
            ],
            "InputOutputToolBox": [InputQuestionTool()],
            "WebToolBox": [ReadHTMLTool()],
            "TextProcessingToolBox": [GrepAppTool()],
        }
        loaded_tool_names.update(
            sinus.name, cosinus.name, multiply_tool.name, concat_tool.name,
            ListDirectoryTool().name, ReadFileTool().name, WriteFileTool(disable_ensure_tmp_path=True).name,
            ReadFileBlockTool().name, InputQuestionTool().name, ReadHTMLTool().name, GrepAppTool().name
        )

    # Add AgentToolBox regardless of source
    toolboxes["AgentToolBox"] = [AgentTool(model=model)]
    loaded_tool_names.add("agent_tool")
    if history_store is not None:
        toolboxes["AgentToolBox"].append(RetrieveStepTool(history_store))
        loaded_tool_names.add("retrieve_step")

    # Dynamically load additional tools from tools/ directory, avoiding duplicates
    tools_dir: Path = Path(__file__).parent / "tools"
    for tool_file in tools_dir.glob("*.py"):
        if tool_file.stem == "__init__":
            continue
        module = importlib.import_module(f".tools.{tool_file.stem}", package="quantalogic.codeact")
        for name, obj in module.__dict__.items():
            if isinstance(obj, Tool) and hasattr(obj, 'async_execute') and obj.name not in loaded_tool_names:
                toolbox_name = tool_file.stem.capitalize() + "ToolBox"
                if toolbox_name not in toolboxes:
                    toolboxes[toolbox_name] = []
                toolboxes[toolbox_name].append(obj)
                loaded_tool_names.add(obj.name)
                logger.debug(f"Added tool: {name} from {tool_file.stem} to {toolbox_name}")

    return toolboxes


def get_default_tools(model: str, history_store: Optional[List[dict]] = None) -> List[Tool]:
    """Return a flat list of all tools from toolboxes, ensuring no duplicates."""
    toolboxes = get_toolboxes(model, history_store)
    combined_tools = []
    seen_names = set()
    
    for tools in toolboxes.values():
        for tool in tools:
            if tool.name not in seen_names:
                combined_tools.append(tool)
                seen_names.add(tool.name)
    
    logger.info(f"Loaded {len(combined_tools)} default tools: {[tool.name for tool in combined_tools]}")
    return combined_tools