"""High-level interface for the Quantalogic Agent with modular configuration."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Union

import yaml
from jinja2 import Environment
from lxml import etree

from quantalogic.tools import Tool

from .constants import MAX_HISTORY_TOKENS, MAX_TOKENS
from .executor import BaseExecutor, Executor
from .llm_util import litellm_completion
from .plugin_manager import PluginManager
from .react_agent import ReActAgent
from .reasoner import BaseReasoner, Reasoner
from .templates import jinja_env as default_jinja_env
from .tools_manager import RetrieveStepTool, get_default_tools
from .utils import process_tools


@dataclass
class AgentConfig:
    """Configuration for the Agent loaded from a YAML file or direct arguments."""
    model: str = "gemini/gemini-2.0-flash"
    max_iterations: int = 5
    tools: Optional[List[Union[Tool, Callable]]] = None
    max_history_tokens: int = MAX_HISTORY_TOKENS
    toolbox_directory: str = "toolboxes"
    enabled_toolboxes: Optional[List[str]] = None
    reasoner_name: str = "default"
    executor_name: str = "default"

    def __init__(
        self,
        model: str = "gemini/gemini-2.0-flash",
        max_iterations: int = 5,
        tools: Optional[List[Union[Tool, Callable]]] = None,
        max_history_tokens: int = MAX_HISTORY_TOKENS,
        toolbox_directory: str = "toolboxes",
        enabled_toolboxes: Optional[List[str]] = None,
        reasoner_name: str = "default",
        executor_name: str = "default",
        config_file: Optional[str] = None
    ) -> None:
        if config_file:
            try:
                with open(Path(__file__).parent / config_file) as f:
                    config: Dict = yaml.safe_load(f) or {}
                self.model = config.get("model", model)
                self.max_iterations = config.get("max_iterations", max_iterations)
                self.max_history_tokens = config.get("max_history_tokens", max_history_tokens)
                self.toolbox_directory = config.get("toolbox_directory", toolbox_directory)
                self.tools = tools  # Tools still come from parameter, not config
                self.enabled_toolboxes = config.get("enabled_toolboxes", enabled_toolboxes)
                self.reasoner_name = config.get("reasoner", reasoner_name)
                self.executor_name = config.get("executor", executor_name)
            except FileNotFoundError:
                self._set_defaults(model, max_iterations, max_history_tokens, toolbox_directory, 
                                 tools, enabled_toolboxes, reasoner_name, executor_name)
        else:
            self._set_defaults(model, max_iterations, max_history_tokens, toolbox_directory, 
                             tools, enabled_toolboxes, reasoner_name, executor_name)

    def _set_defaults(self, model, max_iterations, max_history_tokens, toolbox_directory, 
                     tools, enabled_toolboxes, reasoner_name, executor_name):
        self.model = model
        self.max_iterations = max_iterations
        self.max_history_tokens = max_history_tokens
        self.toolbox_directory = toolbox_directory
        self.tools = tools
        self.enabled_toolboxes = enabled_toolboxes
        self.reasoner_name = reasoner_name
        self.executor_name = executor_name


class Agent:
    """High-level interface for the Quantalogic Agent with modular configuration."""
    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        personality: Optional[str] = None,
        backstory: Optional[str] = None,
        sop: Optional[str] = None,
        jinja_env: Optional[Environment] = None
    ) -> None:
        config = config or AgentConfig()
        self.plugin_manager = PluginManager()
        self.plugin_manager.load_plugins()
        self.model: str = config.model
        self.default_tools: List[Tool] = (
            process_tools(config.tools)
            if config.tools is not None
            else get_default_tools(self.model, enabled_toolboxes=config.enabled_toolboxes)
        )
        self.max_iterations: int = config.max_iterations
        self.personality: Optional[str] = personality
        self.backstory: Optional[str] = backstory
        self.sop: Optional[str] = sop
        self.max_history_tokens: int = config.max_history_tokens
        self.jinja_env: Environment = jinja_env or default_jinja_env
        self._observers: List[Tuple[Callable, List[str]]] = []
        self.last_solve_context_vars: Dict = {}
        self.default_reasoner_name: str = config.reasoner_name
        self.default_executor_name: str = config.executor_name

    def _build_system_prompt(self) -> str:
        """Builds a system prompt based on personality, backstory, and SOP."""
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
        streaming: bool = False,
        reasoner_name: Optional[str] = None,
        executor_name: Optional[str] = None
    ) -> str:
        """Single-step interaction with optional custom tools and streaming."""
        system_prompt: str = self._build_system_prompt()
        if use_tools:
            chat_tools: List[Tool] = process_tools(tools) if tools is not None else self.default_tools
            reasoner_name = reasoner_name or self.default_reasoner_name
            executor_name = executor_name or self.default_executor_name
            reasoner_cls = self.plugin_manager.reasoners.get(reasoner_name, Reasoner)
            executor_cls = self.plugin_manager.executors.get(executor_name, Executor)
            chat_agent = ReActAgent(
                model=self.model,
                tools=chat_tools,
                max_iterations=1,
                max_history_tokens=self.max_history_tokens,
                reasoner=reasoner_cls(self.model, chat_tools),
                executor=executor_cls(chat_tools, self._notify_observers)
            )
            chat_agent.executor.register_tool(RetrieveStepTool(chat_agent.history_manager.store))
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
        """Synchronous wrapper for chat."""
        return asyncio.run(self.chat(message, timeout=timeout))

    async def solve(
        self,
        task: str,
        success_criteria: Optional[str] = None,
        max_iterations: Optional[int] = None,
        tools: Optional[List[Union[Tool, Callable]]] = None,
        timeout: int = 300,
        streaming: bool = False,
        reasoner_name: Optional[str] = None,
        executor_name: Optional[str] = None
    ) -> List[Dict]:
        """Multi-step task solving with optional custom tools, max_iterations, and streaming."""
        system_prompt: str = self._build_system_prompt()
        solve_tools: List[Tool] = process_tools(tools) if tools is not None else self.default_tools
        reasoner_name = reasoner_name or self.default_reasoner_name
        executor_name = executor_name or self.default_executor_name
        reasoner_cls = self.plugin_manager.reasoners.get(reasoner_name, Reasoner)
        executor_cls = self.plugin_manager.executors.get(executor_name, Executor)
        solve_agent = ReActAgent(
            model=self.model,
            tools=solve_tools,
            max_iterations=max_iterations if max_iterations is not None else self.max_iterations,
            max_history_tokens=self.max_history_tokens,
            reasoner=reasoner_cls(self.model, solve_tools),
            executor=executor_cls(solve_tools, self._notify_observers)
        )
        solve_agent.executor.register_tool(RetrieveStepTool(solve_agent.history_manager.store))
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
        """Synchronous wrapper for solve."""
        return asyncio.run(self.solve(task, success_criteria, timeout=timeout))

    def add_observer(self, observer: Callable, event_types: List[str]) -> 'Agent':
        """Add an observer to be applied to agents created in chat and solve."""
        self._observers.append((observer, event_types))
        return self

    def register_tool(self, tool: Tool) -> None:
        """Register a new tool dynamically at runtime."""
        if tool.name in [t.name for t in self.default_tools]:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self.default_tools.append(tool)
        self.plugin_manager.tools.register(tool)

    def register_reasoner(self, reasoner: BaseReasoner, name: str) -> None:
        """Register a new reasoner dynamically at runtime."""
        self.plugin_manager.reasoners[name] = reasoner.__class__

    def register_executor(self, executor: BaseExecutor, name: str) -> None:
        """Register a new executor dynamically at runtime."""
        self.plugin_manager.executors[name] = executor.__class__

    def list_tools(self) -> List[str]:
        """Return a list of available tool names."""
        return [tool.name for tool in self.default_tools]

    def get_context_vars(self) -> Dict:
        """Return the context variables from the last solve call."""
        return self.last_solve_context_vars

    def _extract_response(self, history: List[Dict]) -> str:
        """Extract a clean response from the history."""
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