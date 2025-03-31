"""Tool management module for defining and retrieving agent tools."""

import asyncio
import importlib
import inspect
import os
import re
import subprocess
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
        self.tools[tool.name] = tool
        logger.debug(f"Tool registered: {tool.name}")

    def get_tools(self) -> List[Tool]:
        """Return all registered tools."""
        logger.debug(f"Returning {len(self.tools)} tools: {list(self.tools.keys())}")
        return list(self.tools.values())

    def register_tools_from_module(self, module) -> None:
        """Register all @create_tool generated Tool instances from a module."""
        tools_found = False
        for name, obj in inspect.getmembers(module):
            # Check if the object is a Tool instance created by create_tool
            if isinstance(obj, Tool) and hasattr(obj, '_func'):
                self.register(obj)
                logger.debug(f"Registered tool: {obj.name} from {module.__name__}")
                tools_found = True
        if not tools_found:
            logger.warning(f"No @create_tool generated tools found in {module.__name__}")

    def extract_uv_dependencies(self, script_path: Path) -> list[str]:
        """Extract the dependencies list from the uv metadata in a script."""
        with open(script_path, 'r') as f:
            content = f.read()
        
        # Find the metadata block
        match = re.search(r'# /// script\n(.*?)\n# ///', content, re.DOTALL)
        if not match:
            logger.debug(f"No uv metadata found in {script_path}")
            return []
        
        metadata = match.group(1)
        
        # Extract the dependencies list
        deps_match = re.search(r'dependencies = \[\n(.*?)\n\]', metadata, re.DOTALL)
        if not deps_match:
            logger.debug(f"No dependencies section found in uv metadata of {script_path}")
            return []
        
        deps_str = deps_match.group(1)
        dependencies = []
        for line in deps_str.splitlines():
            line = line.strip()
            if line and line != ',':
                # Remove trailing comma and quotes
                if line.endswith(','):
                    line = line[:-1]
                dep = line.strip('"').strip("'")
                dependencies.append(dep)
        
        logger.debug(f"Extracted dependencies from {script_path}: {dependencies}")
        return dependencies

    def install_uv_dependencies(self, dependencies: list[str]) -> None:
        """Install dependencies using uv pip install."""
        if not dependencies:
            logger.debug("No dependencies to install")
            return
        cmd = ['uv', 'pip', 'install'] + dependencies
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"Installed dependencies: {dependencies}")
            logger.debug(f"Installation output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install dependencies: {e.stderr}")
            raise

    def load_toolboxes(self, directory: str = "toolboxes") -> None:
        """Load all toolboxes from the specified directory with dependency installation."""
        toolbox_dir = Path(__file__).parent / directory
        logger.debug(f"Attempting to load toolboxes from: {toolbox_dir}")
        
        if not toolbox_dir.exists() or not toolbox_dir.is_dir():
            logger.warning(f"Toolbox directory not found or invalid: {toolbox_dir}")
            return

        # Collect all dependencies across toolboxes to install once
        all_dependencies = set()
        for tool_file in toolbox_dir.glob("*.py"):
            if tool_file.stem == "__init__":
                continue
            dependencies = self.extract_uv_dependencies(tool_file)
            all_dependencies.update(dependencies)

        # Install all dependencies in one go
        if all_dependencies:
            self.install_uv_dependencies(list(all_dependencies))

        # Import and register tools after dependencies are installed
        for tool_file in toolbox_dir.glob("*.py"):
            if tool_file.stem == "__init__":
                continue
            module_name = f"quantalogic.codeact.{directory}.{tool_file.stem}"
            logger.debug(f"Attempting to import module: {module_name}")
            try:
                module = importlib.import_module(module_name)
                self.register_tools_from_module(module)
                logger.info(f"Successfully loaded toolbox: {module_name}")
            except ImportError as e:
                logger.error(f"Failed to import toolbox {module_name}: {e}")


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
    """Dynamically load default tools from the tools/ directory and toolboxes.

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

    # Load tools from toolboxes directory
    registry.load_toolboxes("toolboxes")

    combined_tools = registry.get_tools()
    logger.info(f"Loaded {len(combined_tools)} default tools: {[tool.name for tool in combined_tools]}")
    return combined_tools