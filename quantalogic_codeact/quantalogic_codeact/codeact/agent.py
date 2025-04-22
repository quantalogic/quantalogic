"""High-level interface for the Quantalogic Agent with modular configuration."""

import asyncio
import os
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from jinja2 import Environment
from loguru import logger

from quantalogic.tools import Tool

from .agent_config import AgentConfig
from .codeact_agent import CodeActAgent
from .constants import MAX_TOKENS
from .conversation_history_manager import ConversationHistoryManager
from .executor import BaseExecutor, Executor
from .plugin_manager import PluginManager
from .reasoner import BaseReasoner, Reasoner
from .tools import RetrieveStepTool
from .tools_manager import get_default_tools
from .utils import process_tools


class Agent:
    """High-level interface for the Quantalogic Agent with unified configuration."""
    
    def __init__(
        self,
        config: Union[AgentConfig, str, None] = None
    ) -> None:
        """Initialize the agent with a configuration."""
        try:
            if isinstance(config, str):
                config = AgentConfig(config_file=config)
            elif config is None:
                config = AgentConfig()
            elif not isinstance(config, AgentConfig):
                raise ValueError("Config must be an AgentConfig instance or a string path to a config file.")
        except Exception as e:
            logger.error(f"Failed to initialize config: {e}. Using default configuration.")
            config = AgentConfig()

        self.config = config
        self.plugin_manager = PluginManager()
        try:
            self.plugin_manager.load_plugins()
        except Exception as e:
            logger.error(f"Failed to load plugins: {e}")
        self.model: str = config.model
        self.temperature: float = config.temperature  # Added temperature
        self.default_tools: List[Tool] = self._get_tools()
        # If no tools are loaded, do not fall back to all registered tools
        if not self.default_tools and (not config.enabled_toolboxes or not config.tools):
            logger.info("No tools loaded from configuration; no toolboxes specified.")
        self.max_iterations: int = config.max_iterations
        self.personality = config.personality
        self.backstory = config.backstory
        self.sop: Optional[str] = config.sop
        self.name: Optional[str] = config.name
        self.max_history_tokens: int = config.max_history_tokens
        self.jinja_env: Environment = config.jinja_env
        self._observers: List[Tuple[Callable, List[str]]] = []
        self.last_solve_context_vars: Dict = {}
        self.default_reasoner_name: str = config.reasoner.get("name", config.reasoner_name)
        self.default_executor_name: str = config.executor.get("name", config.executor_name)
        self.conversation_history_manager = ConversationHistoryManager(max_tokens=self.max_history_tokens)
        self.react_agent = CodeActAgent(
            model=self.model,
            tools=self.default_tools,
            max_iterations=self.max_iterations,
            max_history_tokens=self.max_history_tokens,
            system_prompt=self._build_system_prompt(),
            reasoner=Reasoner(self.model, self.default_tools, temperature=self.temperature),
            executor=Executor(self.default_tools, self._notify_observers),
            conversation_history_manager=self.conversation_history_manager,
            temperature=self.temperature  # Pass temperature
        )

    def _get_tools(self) -> List[Tool]:
        """Load tools, applying tools_config if provided."""
        try:
            base_tools = (
                process_tools(self.config.tools)
                if self.config.tools is not None
                else get_default_tools(self.model, enabled_toolboxes=self.config.enabled_toolboxes)
            )
            if not self.config.tools_config:
                return base_tools
            
            self._resolve_secrets(self.config.tools_config)
            filtered_tools = []
            processed_names = set()
            for tool_conf in self.config.tools_config:
                tool_name = tool_conf.get("name")
                if tool_conf.get("enabled", True):
                    tool = next((t for t in base_tools if t.name == tool_name or t.toolbox_name == tool_name), None)
                    if tool and tool.name not in processed_names:
                        for key, value in tool_conf.items():
                            if key not in ["name", "enabled"]:
                                setattr(tool, key, value)
                        filtered_tools.append(tool)
                        processed_names.add(tool.name)
            for tool in base_tools:
                if tool.name not in processed_names:
                    filtered_tools.append(tool)
            logger.info(f"Loaded {len(filtered_tools)} tools successfully.")
            return filtered_tools
        except Exception as e:
            logger.error(f"Error loading tools: {e}. Returning empty toolset.")
            return []

    def _resolve_secrets(self, config_dict: List[Dict[str, Any]]) -> None:
        """Resolve environment variable placeholders in tools_config."""
        try:
            for item in config_dict:
                for key, value in item.items():
                    if isinstance(value, str) and "{{ env." in value:
                        env_var = value.split("{{ env.")[1].split("}}")[0]
                        item[key] = os.getenv(env_var, value)
                    elif isinstance(value, dict):
                        self._resolve_secrets([value])
        except Exception as e:
            logger.error(f"Error resolving secrets in tools_config: {e}")

    def _build_system_prompt(self) -> str:
        """Build a system prompt based on name, personality, backstory, and SOP."""
        try:
            prompt = f"I am {self.name}, an AI assistant." if self.name else "You are an AI assistant."
            if self.personality:
                if isinstance(self.personality, str):
                    prompt += f" I have a {self.personality} personality."
                elif isinstance(self.personality, dict):
                    traits = self.personality.get("traits", [])
                    if traits:
                        prompt += f" I have the following personality traits: {', '.join(traits)}."
                    tone = self.personality.get("tone")
                    if tone:
                        prompt += f" My tone is {tone}."
                    humor = self.personality.get("humor_level")
                    if humor:
                        prompt += f" My humor level is {humor}."
            if self.backstory:
                if isinstance(self.backstory, str):
                    prompt += f" My backstory is: {self.backstory}"
                elif isinstance(self.backstory, dict):
                    origin = self.backstory.get("origin")
                    if origin:
                        prompt += f" I was created by {origin}."
                    purpose = self.backstory.get("purpose")
                    if purpose:
                        prompt += f" My purpose is {purpose}."
                    experience = self.backstory.get("experience")
                    if experience:
                        prompt += f" My experience includes: {experience}"
            if self.sop:
                prompt += f" Follow this standard operating procedure: {self.sop}"
            return prompt
        except Exception as e:
            logger.error(f"Error building system prompt: {e}. Using default.")
            return "You are an AI assistant."

    async def chat(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        use_tools: bool = False,
        timeout: int = 30,
        max_tokens: int = MAX_TOKENS,
        temperature: float = None,  # Allow override
        streaming: bool = False,
        reasoner_name: Optional[str] = None,
        executor_name: Optional[str] = None
    ) -> str:
        """Single-step interaction with optional custom tools, history, and streaming."""
        try:
            logger.debug(f"Agent.chat called with message={message!r}, use_tools={use_tools}, timeout={timeout}, max_tokens={max_tokens}, temperature={temperature}, streaming={streaming}, reasoner_name={reasoner_name}, executor_name={executor_name}")
            logger.info(f"Invoking react_agent.chat for simple chat with message={message!r}, streaming={streaming}")
            response: str = await self.react_agent.chat(
                message,
                max_tokens=max_tokens,
                temperature=temperature,
                streaming=streaming
            )
            logger.info(f"Chat response (no tools): {response}")
            # Update conversation history
            self.conversation_history_manager.add_message("user", message)
            self.conversation_history_manager.add_message("assistant", response)
            return response
        except Exception as e:
            logger.exception("Exception in Agent.chat")
            logger.error(f"Chat failed: {e}")
            return f"Error: Unable to process chat request due to {str(e)}"

    def sync_chat(self, message: str, timeout: int = 30) -> str:
        """Synchronous wrapper for chat."""
        try:
            return asyncio.run(self.chat(message, timeout=timeout))
        except Exception as e:
            logger.error(f"Synchronous chat failed: {e}")
            return f"Error: {str(e)}"

    async def solve(
        self,
        task: str,
        history: Optional[List[Dict[str, str]]] = None,
        success_criteria: Optional[str] = None,
        task_goal: Optional[str] = None,
        max_iterations: Optional[int] = None,
        tools: Optional[List[Union[Tool, Callable]]] = None,
        timeout: int = 300,
        streaming: bool = False,
        reasoner_name: Optional[str] = None,
        executor_name: Optional[str] = None
    ) -> List[Dict]:
        """Multi-step task solving with optional custom tools, history, max_iterations, and streaming."""
        try:
            system_prompt: str = self._build_system_prompt()
            solve_tools: List[Tool] = process_tools(tools) if tools is not None else self.default_tools
            reasoner_name = reasoner_name or self.default_reasoner_name
            executor_name = executor_name or self.default_executor_name
            reasoner_cls = self.plugin_manager.reasoners.get(reasoner_name, Reasoner)
            executor_cls = self.plugin_manager.executors.get(executor_name, Executor)
            reasoner_config = self.config.reasoner.get("config", {})
            executor_config = self.config.executor.get("config", {})
            # Format history as a string for the system prompt
            history_str = ""
            if history:
                history_str = "\n".join(
                    f"{msg['role'].capitalize()}: {msg['content']}" 
                    for msg in history
                )
                system_prompt += f"\n\nPrevious conversation:\n{history_str}"
            solve_agent = CodeActAgent(
                model=self.model,
                tools=solve_tools,
                max_iterations=max_iterations if max_iterations is not None else self.max_iterations,
                max_history_tokens=self.max_history_tokens,
                system_prompt=system_prompt,
                reasoner=reasoner_cls(self.model, solve_tools, temperature=self.temperature, **reasoner_config),
                executor=executor_cls(solve_tools, self._notify_observers, **executor_config),
                conversation_history_manager=self.conversation_history_manager,
                temperature=self.temperature
            )
            solve_agent.executor.register_tool(RetrieveStepTool(solve_agent.history_manager.store))
            for observer, event_types in self._observers:
                solve_agent.add_observer(observer, event_types)
            
            history_result: List[Dict] = await solve_agent.solve(
                task,
                success_criteria,
                task_goal=task_goal,
                system_prompt=system_prompt,
                max_iterations=max_iterations,
                streaming=streaming
            )
            self.last_solve_context_vars = solve_agent.context_vars.copy()
            # Update conversation history
            self.conversation_history_manager.add_message("user", f"Task: {task}")
            final_answer = history_result[-1].get("result", "")
            self.conversation_history_manager.add_message("assistant", final_answer)
            return history_result
        except Exception as e:
            logger.error(f"Solve failed: {e}")
            return [{"error": f"Failed to solve task: {str(e)}"}]

    def sync_solve(self, task: str, success_criteria: Optional[str] = None, task_goal: Optional[str] = None, timeout: int = 300) -> List[Dict]:
        """Synchronous wrapper for solve."""
        try:
            return asyncio.run(self.solve(task, success_criteria=success_criteria, task_goal=task_goal, timeout=timeout))
        except Exception as e:
            logger.error(f"Synchronous solve failed: {e}")
            return [{"error": f"Failed to solve task synchronously: {str(e)}"}]

    def add_observer(self, observer: Callable, event_types: List[str]) -> 'Agent':
        """Add an observer to both the Agent and its internal react_agent."""
        try:
            self._observers.append((observer, event_types))
            self.react_agent.add_observer(observer, event_types)
            return self
        except Exception as e:
            logger.error(f"Failed to add observer: {e}")
            raise

    def remove_observer(self, observer: Callable):
        """Remove an observer from both the Agent and its internal react_agent."""
        try:
            self._observers = [obs for obs in self._observers if obs[0] != observer]
            self.react_agent._observers = [obs for obs in self.react_agent._observers if obs[0] != observer]
        except Exception as e:
            logger.error(f"Failed to remove observer: {e}")
            raise

    def register_tool(self, tool: Tool) -> None:
        """Register a new tool dynamically at runtime."""
        try:
            if tool.name in [t.name for t in self.default_tools]:
                raise ValueError(f"Tool '{tool.name}' is already registered")
            self.default_tools.append(tool)
            self.plugin_manager.tools.register(tool)
        except Exception as e:
            logger.error(f"Failed to register tool {tool.name}: {e}")
            raise

    def register_reasoner(self, reasoner: BaseReasoner, name: str) -> None:
        """Register a new reasoner dynamically at runtime."""
        try:
            self.plugin_manager.reasoners[name] = reasoner.__class__
        except Exception as e:
            logger.error(f"Failed to register reasoner {name}: {e}")
            raise

    def register_executor(self, executor: BaseExecutor, name: str) -> None:
        """Register a new executor dynamically at runtime."""
        try:
            self.plugin_manager.executors[name] = executor.__class__
        except Exception as e:
            logger.error(f"Failed to register executor {name}: {e}")
            raise

    def list_tools(self) -> List[str]:
        """Return a list of available tool names."""
        try:
            return [tool.name for tool in self.default_tools]
        except Exception as e:
            logger.error(f"Error listing tools: {e}")
            return []

    def get_context_vars(self) -> Dict:
        """Return the context variables from the last solve call."""
        try:
            return self.last_solve_context_vars
        except Exception as e:
            logger.error(f"Error getting context vars: {e}")
            return {}

    async def _notify_observers(self, event: object) -> None:
        """Notify all subscribed observers of an event."""
        try:
            await asyncio.gather(
                *(observer(event) for observer, types in self._observers if event.event_type in types),
                return_exceptions=True
            )
        except Exception as e:
            logger.error(f"Error notifying observers: {e}")