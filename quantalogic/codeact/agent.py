"""High-level interface for the Quantalogic Agent with modular configuration."""

import asyncio
import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Union

import yaml
from jinja2 import Environment
from lxml import etree

from quantalogic.tools import Tool, create_tool

from .constants import MAX_HISTORY_TOKENS, MAX_TOKENS
from .llm_util import litellm_completion
from .react_agent import ReActAgent
from .templates import jinja_env as default_jinja_env
from .tools_manager import RetrieveStepTool, get_default_tools


@dataclass
class AgentConfig:
    """Configuration for the Agent loaded from a YAML file or direct arguments.

    Attributes:
        model (str): The language model to use.
        max_iterations (int): Maximum number of reasoning steps.
        tools (Optional[List[Union[Tool, Callable]]]): List of tools or async functions.
        max_history_tokens (int): Token limit for history formatting.
    """
    model: str = "gemini/gemini-2.0-flash"
    max_iterations: int = 5
    tools: Optional[List[Union[Tool, Callable]]] = None
    max_history_tokens: int = MAX_HISTORY_TOKENS

    def __init__(
        self,
        model: str = "gemini/gemini-2.0-flash",
        max_iterations: int = 5,
        tools: Optional[List[Union[Tool, Callable]]] = None,
        max_history_tokens: int = MAX_HISTORY_TOKENS,
        config_file: Optional[str] = None
    ) -> None:
        """Initialize AgentConfig with direct arguments or from a YAML file.

        Args:
            model (str): The language model to use.
            max_iterations (int): Maximum number of reasoning steps.
            tools (Optional[List[Union[Tool, Callable]]]): List of tools or async functions.
            max_history_tokens (int): Token limit for history formatting.
            config_file (Optional[str]): Path to a YAML config file to override defaults.
        """
        if config_file:
            try:
                with open(Path(__file__).parent / config_file) as f:
                    config: Dict = yaml.safe_load(f) or {}
                self.model = config.get("model", model)
                self.max_iterations = config.get("max_iterations", max_iterations)
                self.max_history_tokens = config.get("max_history_tokens", max_history_tokens)
                self.tools = tools  # Tools are not loaded from YAML in this case
            except FileNotFoundError:
                # Fall back to provided arguments if file not found
                self.model = model
                self.max_iterations = max_iterations
                self.max_history_tokens = max_history_tokens
                self.tools = tools
        else:
            self.model = model
            self.max_iterations = max_iterations
            self.max_history_tokens = max_history_tokens
            self.tools = tools


class Agent:
    """High-level interface for the Quantalogic Agent with modular configuration.

    This class provides methods for single-step chats and multi-step task solving,
    with support for custom tools, personality, and event observers.

    Attributes:
        model (str): The language model in use.
        default_tools (List[Tool]): Default set of tools available.
        max_iterations (int): Maximum steps for solving tasks.
        personality (Optional[str]): Agent's personality description.
        backstory (Optional[str]): Agent's backstory.
        sop (Optional[str]): Standard operating procedure.
        max_history_tokens (int): Token limit for history.
        jinja_env (Environment): Jinja2 environment for templates.
        _observers (List[Tuple[Callable, List[str]]]): Event observers.
        last_solve_context_vars (Dict): Context vars from last solve call.
    """
    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        personality: Optional[str] = None,
        backstory: Optional[str] = None,
        sop: Optional[str] = None,
        jinja_env: Optional[Environment] = None
    ) -> None:
        config = config or AgentConfig()
        self.model: str = config.model
        self.default_tools: List[Tool] = self._process_tools(config.tools) if config.tools is not None else get_default_tools(config.model)
        self.max_iterations: int = config.max_iterations
        self.personality: Optional[str] = personality
        self.backstory: Optional[str] = backstory
        self.sop: Optional[str] = sop
        self.max_history_tokens: int = config.max_history_tokens
        self.jinja_env: Environment = jinja_env or default_jinja_env
        self._observers: List[Tuple[Callable, List[str]]] = []
        self.last_solve_context_vars: Dict = {}

    def _process_tools(self, tools: List[Union[Tool, Callable]]) -> List[Tool]:
        """Process a list of tools or async functions into Tool instances.

        Args:
            tools (List[Union[Tool, Callable]]): Tools or functions to process.

        Returns:
            List[Tool]: Processed tool instances.

        Raises:
            ValueError: If a callable is not async or an item is invalid.
        """
        processed_tools: List[Tool] = []
        for tool in tools:
            if isinstance(tool, Tool):
                processed_tools.append(tool)
            elif callable(tool):
                if not inspect.iscoroutinefunction(tool):
                    raise ValueError(f"Callable '{tool.__name__}' must be an async function to be used as a tool.")
                processed_tools.append(create_tool(tool))
            else:
                raise ValueError(f"Invalid item type: {type(tool)}. Expected Tool or async function.")
        return processed_tools

    def _build_system_prompt(self) -> str:
        """Builds a system prompt based on personality, backstory, and SOP.

        Returns:
            str: The constructed system prompt.
        """
        prompt: str = "You are an AI assistant."
        if self.personality:
            prompt += f" You have a {self.personality} personality."
        if self.backstory:
            prompt += f" Your backstory is: {self.backstory}"
        if self.sop:
            prompt += f" Follow this standard operating procedure: {self.sop}"
        return prompt

    async def chat(
        self,
        message: str,
        use_tools: bool = False,
        tools: Optional[List[Union[Tool, Callable]]] = None,
        timeout: int = 30,
        max_tokens: int = MAX_TOKENS,
        temperature: float = 0.7,
        streaming: bool = False
    ) -> str:
        """Single-step interaction with optional custom tools and streaming.

        Args:
            message (str): User input message.
            use_tools (bool): Whether to use tools.
            tools (Optional[List[Union[Tool, Callable]]]): Custom tools to use.
            timeout (int): Timeout in seconds.
            max_tokens (int): Maximum tokens for response.
            temperature (float): Sampling temperature.
            streaming (bool): Whether to stream the response.

        Returns:
            str: The generated response.
        """
        system_prompt: str = self._build_system_prompt()
        if use_tools:
            chat_tools: List[Tool] = self._process_tools(tools) if tools is not None else self.default_tools
            chat_agent = ReActAgent(
                model=self.model,
                tools=chat_tools,
                max_iterations=1,
                max_history_tokens=self.max_history_tokens
            )
            chat_agent.executor.register_tool(RetrieveStepTool(chat_agent.history_store))
            for observer, event_types in self._observers:
                chat_agent.add_observer(observer, event_types)
            history: List[Dict] = await chat_agent.solve(message, system_prompt=system_prompt, streaming=streaming)
            return self._extract_response(history)
        else:
            response: str = await litellm_completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                stream=streaming,
                notify_event=self._notify_observers if streaming else None
            )
            return response.strip()

    def sync_chat(self, message: str, timeout: int = 30) -> str:
        """Synchronous wrapper for chat.

        Args:
            message (str): User input message.
            timeout (int): Timeout in seconds.

        Returns:
            str: The generated response.
        """
        return asyncio.run(self.chat(message, timeout=timeout))

    async def solve(
        self,
        task: str,
        success_criteria: Optional[str] = None,
        max_iterations: Optional[int] = None,
        tools: Optional[List[Union[Tool, Callable]]] = None,
        timeout: int = 300,
        streaming: bool = False
    ) -> List[Dict]:
        """Multi-step task solving with optional custom tools, max_iterations, and streaming.

        Args:
            task (str): The task to solve.
            success_criteria (Optional[str]): Criteria for completion.
            max_iterations (Optional[int]): Override for max steps.
            tools (Optional[List[Union[Tool, Callable]]]): Custom tools.
            timeout (int): Timeout in seconds.
            streaming (bool): Whether to stream responses.

        Returns:
            List[Dict]: History of steps taken.
        """
        system_prompt: str = self._build_system_prompt()
        solve_tools: List[Tool] = self._process_tools(tools) if tools is not None else self.default_tools
        solve_agent = ReActAgent(
            model=self.model,
            tools=solve_tools,
            max_iterations=max_iterations if max_iterations is not None else self.max_iterations,
            max_history_tokens=self.max_history_tokens
        )
        solve_agent.executor.register_tool(RetrieveStepTool(solve_agent.history_store))
        for observer, event_types in self._observers:
            solve_agent.add_observer(observer, event_types)
        
        history: List[Dict] = await solve_agent.solve(
            task,
            success_criteria,
            system_prompt=system_prompt,
            max_iterations=max_iterations,
            streaming=streaming
        )
        self.last_solve_context_vars = solve_agent.context_vars.copy()
        return history

    def sync_solve(self, task: str, success_criteria: Optional[str] = None, timeout: int = 300) -> List[Dict]:
        """Synchronous wrapper for solve.

        Args:
            task (str): The task to solve.
            success_criteria (Optional[str]): Criteria for completion.
            timeout (int): Timeout in seconds.

        Returns:
            List[Dict]: History of steps taken.
        """
        return asyncio.run(self.solve(task, success_criteria, timeout=timeout))

    def add_observer(self, observer: Callable, event_types: List[str]) -> 'Agent':
        """Add an observer to be applied to agents created in chat and solve.

        Args:
            observer (Callable): Function to call when events occur.
            event_types (List[str]): List of event type names.

        Returns:
            Agent: Self, for method chaining.
        """
        self._observers.append((observer, event_types))
        return self

    def register_tool(self, tool: Tool) -> None:
        """Register a new tool dynamically at runtime.

        Args:
            tool (Tool): The tool to register.

        Raises:
            ValueError: If the tool name is already registered.
        """
        if tool.name in [t.name for t in self.default_tools]:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self.default_tools.append(tool)

    def list_tools(self) -> List[str]:
        """Return a list of available tool names.

        Returns:
            List[str]: Names of registered tools.
        """
        return [tool.name for tool in self.default_tools]

    def get_context_vars(self) -> Dict:
        """Return the context variables from the last solve call.

        Returns:
            Dict: Context variables.
        """
        return self.last_solve_context_vars

    def _extract_response(self, history: List[Dict]) -> str:
        """Extract a clean response from the history.

        Args:
            history (List[Dict]): Steps from a solve operation.

        Returns:
            str: Extracted response or error message.
        """
        if not history:
            return "No response generated."
        last_result: str = history[-1]["result"]
        try:
            root = etree.fromstring(last_result)
            if root.findtext("Status") == "Success":
                value: str = root.findtext("Value") or ""
                final_answer: Optional[str] = root.findtext("FinalAnswer")
                return final_answer.strip() if final_answer else value.strip()
            else:
                return f"Error: {root.findtext('Value') or 'Unknown error'}"
        except etree.XMLSyntaxError:
            return last_result

    async def _notify_observers(self, event: object) -> None:
        """Notify all subscribed observers of an event."""
        await asyncio.gather(
            *(observer(event) for observer, types in self._observers if event.event_type in types),
            return_exceptions=True
        )