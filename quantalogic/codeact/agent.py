"""High-level interface for the Quantalogic Agent with modular configuration."""

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import yaml
from jinja2 import Environment
from loguru import logger
from lxml import etree

from quantalogic.tools import Tool

from .constants import MAX_HISTORY_TOKENS, MAX_TOKENS
from .conversation_history_manager import ConversationHistoryManager
from .executor import BaseExecutor, Executor
from .plugin_manager import PluginManager
from .react_agent import ReActAgent
from .reasoner import BaseReasoner, Reasoner
from .templates import jinja_env as default_jinja_env
from .tools_manager import RetrieveStepTool, get_default_tools
from .utils import process_tools


@dataclass
class AgentConfig:
    """Comprehensive configuration for the Agent, loadable from a YAML file or direct arguments."""
    model: str = "gemini/gemini-2.0-flash"
    max_iterations: int = 5
    tools: Optional[List[Union[Tool, Callable]]] = None
    max_history_tokens: int = MAX_HISTORY_TOKENS
    toolbox_directory: str = "toolboxes"
    enabled_toolboxes: Optional[List[str]] = None
    reasoner_name: str = "default"
    executor_name: str = "default"
    personality: Optional[str] = None
    backstory: Optional[str] = None
    sop: Optional[str] = None
    jinja_env: Optional[Environment] = None
    name: Optional[str] = None
    tools_config: Optional[List[Dict[str, Any]]] = None
    reasoner: Optional[Dict[str, Any]] = field(default_factory=lambda: {"name": "default"})
    executor: Optional[Dict[str, Any]] = field(default_factory=lambda: {"name": "default"})
    profile: Optional[str] = None
    customizations: Optional[Dict[str, Any]] = None
    agent_tool_model: str = "gemini/gemini-2.0-flash"
    agent_tool_timeout: int = 30

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
        personality: Optional[str] = None,
        backstory: Optional[str] = None,
        sop: Optional[str] = None,
        jinja_env: Optional[Environment] = None,
        config_file: Optional[str] = None,
        name: Optional[str] = None,
        tools_config: Optional[List[Dict[str, Any]]] = None,
        reasoner: Optional[Dict[str, Any]] = None,
        executor: Optional[Dict[str, Any]] = None,
        profile: Optional[str] = None,
        customizations: Optional[Dict[str, Any]] = None,
        agent_tool_model: str = "gemini/gemini-2.0-flash",
        agent_tool_timeout: int = 30
    ) -> None:
        """Initialize configuration from arguments or a YAML file."""
        try:
            if config_file:
                try:
                    with open(Path(__file__).parent / config_file) as f:
                        config: Dict = yaml.safe_load(f) or {}
                    self._load_from_config(config, model, max_iterations, max_history_tokens, toolbox_directory,
                                        tools, enabled_toolboxes, reasoner_name, executor_name, personality,
                                        backstory, sop, jinja_env, name, tools_config, reasoner, executor,
                                        profile, customizations, agent_tool_model, agent_tool_timeout)
                except FileNotFoundError as e:
                    logger.warning(f"Config file {config_file} not found: {e}. Using defaults.")
                    self._set_defaults(model, max_iterations, max_history_tokens, toolbox_directory,
                                    tools, enabled_toolboxes, reasoner_name, executor_name, personality,
                                    backstory, sop, jinja_env, name, tools_config, reasoner, executor,
                                    profile, customizations, agent_tool_model, agent_tool_timeout)
                except yaml.YAMLError as e:
                    logger.error(f"Error parsing YAML config {config_file}: {e}. Falling back to defaults.")
                    self._set_defaults(model, max_iterations, max_history_tokens, toolbox_directory,
                                    tools, enabled_toolboxes, reasoner_name, executor_name, personality,
                                    backstory, sop, jinja_env, name, tools_config, reasoner, executor,
                                    profile, customizations, agent_tool_model, agent_tool_timeout)
            else:
                self._set_defaults(model, max_iterations, max_history_tokens, toolbox_directory,
                                tools, enabled_toolboxes, reasoner_name, executor_name, personality,
                                backstory, sop, jinja_env, name, tools_config, reasoner, executor,
                                profile, customizations, agent_tool_model, agent_tool_timeout)
            self.__post_init__()
        except Exception as e:
            logger.error(f"Failed to initialize AgentConfig: {e}")
            raise

    def _load_from_config(self, config: Dict, *args) -> None:
        """Load configuration from a dictionary, overriding with explicit arguments if provided."""
        try:
            model, max_iterations, max_history_tokens, toolbox_directory, tools, enabled_toolboxes, \
            reasoner_name, executor_name, personality, backstory, sop, jinja_env, name, tools_config, \
            reasoner, executor, profile, customizations, agent_tool_model, agent_tool_timeout = args
            
            self.model = config.get("model", model)
            self.max_iterations = config.get("max_iterations", max_iterations)
            self.max_history_tokens = config.get("max_history_tokens", max_history_tokens)
            self.toolbox_directory = config.get("toolbox_directory", toolbox_directory)
            self.tools = tools if tools is not None else config.get("tools")
            self.enabled_toolboxes = config.get("enabled_toolboxes", enabled_toolboxes)
            self.reasoner = config.get("reasoner", {"name": config.get("reasoner_name", reasoner_name)})
            self.executor = config.get("executor", {"name": config.get("executor_name", executor_name)})
            self.personality = config.get("personality", personality)
            self.backstory = config.get("backstory", backstory)
            self.sop = config.get("sop", sop)
            self.jinja_env = jinja_env or default_jinja_env
            self.name = config.get("name", name)
            self.tools_config = config.get("tools_config", tools_config)
            self.profile = config.get("profile", profile)
            self.customizations = config.get("customizations", customizations)
            self.agent_tool_model = config.get("agent_tool_model", agent_tool_model)
            self.agent_tool_timeout = config.get("agent_tool_timeout", agent_tool_timeout)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            raise

    def _set_defaults(self, model, max_iterations, max_history_tokens, toolbox_directory,
                     tools, enabled_toolboxes, reasoner_name, executor_name, personality,
                     backstory, sop, jinja_env, name, tools_config, reasoner, executor,
                     profile, customizations, agent_tool_model, agent_tool_timeout) -> None:
        """Set default values for all configuration fields."""
        try:
            self.model = model
            self.max_iterations = max_iterations
            self.max_history_tokens = max_history_tokens
            self.toolbox_directory = toolbox_directory
            self.tools = tools
            self.enabled_toolboxes = enabled_toolboxes
            self.reasoner = reasoner if reasoner is not None else {"name": reasoner_name}
            self.executor = executor if executor is not None else {"name": executor_name}
            self.personality = personality
            self.backstory = backstory
            self.sop = sop
            self.jinja_env = jinja_env or default_jinja_env
            self.name = name
            self.tools_config = tools_config
            self.profile = profile
            self.customizations = customizations
            self.agent_tool_model = agent_tool_model
            self.agent_tool_timeout = agent_tool_timeout
        except Exception as e:
            logger.error(f"Error setting defaults: {e}")
            raise

    def __post_init__(self) -> None:
        """Apply profile defaults and customizations after initialization."""
        try:
            profiles = {
                "math_expert": {
                    "personality": {"traits": ["precise", "logical"]},
                    "tools_config": [{"name": "math_tools", "enabled": True}],
                    "sop": "Focus on accuracy and clarity in mathematical solutions."
                },
                "creative_writer": {
                    "personality": {"traits": ["creative", "expressive"]},
                    "tools_config": [{"name": "text_tools", "enabled": True}],
                    "sop": "Generate engaging and imaginative content."
                }
            }
            if self.profile and self.profile in profiles:
                base_config = profiles[self.profile]
                for key, value in base_config.items():
                    if not getattr(self, key) or (key == "personality" and isinstance(getattr(self, key), str)):
                        setattr(self, key, value)
                if self.customizations:
                    for key, value in self.customizations.items():
                        if hasattr(self, key):
                            current = getattr(self, key)
                            if isinstance(current, dict):
                                current.update(value)
                            elif current is None or (key in ["personality", "backstory"] and isinstance(current, str)):
                                setattr(self, key, value)
            # Load enabled_toolboxes from default config if not set
            if self.enabled_toolboxes is None:
                default_config_path = Path.home() / "quantalogic-config.yaml"
                if default_config_path.exists():
                    with open(default_config_path) as f:
                        default_config = yaml.safe_load(f) or {}
                    self.enabled_toolboxes = [tb["name"] for tb in default_config.get("installed_toolboxes", [])]
        except Exception as e:
            logger.error(f"Error in post_init: {e}")
            raise


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
        self.default_tools: List[Tool] = self._get_tools()
        # Fallback: If no tools are loaded, use all registered tools
        if not self.default_tools:
            self.default_tools = self.plugin_manager.tools.get_tools()
            logger.warning(f"No tools loaded from configuration; falling back to all registered tools: {[(t.toolbox_name or 'default', t.name) for t in self.default_tools]}")
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
        self.react_agent = ReActAgent(
            model=self.model,
            tools=self.default_tools,
            max_iterations=self.max_iterations,
            max_history_tokens=self.max_history_tokens,
            system_prompt=self._build_system_prompt(),
            reasoner=Reasoner(self.model, self.default_tools),
            executor=Executor(self.default_tools, self._notify_observers),
            conversation_history_manager=self.conversation_history_manager
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
        tools: Optional[List[Union[Tool, Callable]]] = None,
        timeout: int = 30,
        max_tokens: int = MAX_TOKENS,
        temperature: float = 0.7,
        streaming: bool = False,
        reasoner_name: Optional[str] = None,
        executor_name: Optional[str] = None
    ) -> str:
        """Single-step interaction with optional custom tools, history, and streaming."""
        try:
            system_prompt: str = self._build_system_prompt()
            if use_tools:
                chat_tools: List[Tool] = process_tools(tools) if tools is not None else self.default_tools
                reasoner_name = reasoner_name or self.default_reasoner_name
                executor_name = executor_name or self.default_executor_name
                reasoner_cls = self.plugin_manager.reasoners.get(reasoner_name, Reasoner)
                executor_cls = self.plugin_manager.executors.get(executor_name, Executor)
                reasoner_config = self.config.reasoner.get("config", {})
                executor_config = self.config.executor.get("config", {})
                chat_agent = ReActAgent(
                    model=self.model,
                    tools=chat_tools,
                    max_iterations=1,
                    max_history_tokens=self.max_history_tokens,
                    system_prompt=system_prompt,
                    reasoner=reasoner_cls(self.model, chat_tools, **reasoner_config),
                    executor=executor_cls(chat_tools, self._notify_observers, **executor_config),
                    conversation_history_manager=self.conversation_history_manager
                )
                chat_agent.executor.register_tool(RetrieveStepTool(chat_agent.history_manager.store))
                for observer, event_types in self._observers:
                    chat_agent.add_observer(observer, event_types)
                history_result: List[Dict] = await chat_agent.solve(message, streaming=streaming)
                response = self._extract_response(history_result)
                # Update conversation history
                self.conversation_history_manager.add_message("user", message)
                self.conversation_history_manager.add_message("assistant", response)
                return response
            else:
                response: str = await self.react_agent.chat(message, streaming=streaming)
                # Update conversation history
                self.conversation_history_manager.add_message("user", message)
                self.conversation_history_manager.add_message("assistant", response)
                return response
        except Exception as e:
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
            solve_agent = ReActAgent(
                model=self.model,
                tools=solve_tools,
                max_iterations=max_iterations if max_iterations is not None else self.max_iterations,
                max_history_tokens=self.max_history_tokens,
                system_prompt=system_prompt,
                reasoner=reasoner_cls(self.model, solve_tools, **reasoner_config),
                executor=executor_cls(solve_tools, self._notify_observers, **executor_config),
                conversation_history_manager=self.conversation_history_manager
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
            final_answer = self._extract_response(history_result)
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
        """Add an observer to be applied to agents created in chat and solve."""
        try:
            self._observers.append((observer, event_types))
            return self
        except Exception as e:
            logger.error(f"Failed to add observer: {e}")
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

    def _extract_response(self, history: List[Dict]) -> str:
        """Extract a clean response from the history."""
        try:
            if not history:
                return "No response generated."
            last_result: str = history[-1].get("result", "")
            try:
                root = etree.fromstring(last_result)
                if root.findtext("Status") == "Success":
                    value: str = root.findtext("Value") or ""
                    final_answer: Optional[str] = root.findtext("FinalAnswer")
                    return final_answer.strip() if final_answer else value.strip()
                else:
                    return f"Error: {root.findtext('Value') or 'Unknown error'}"
            except etree.XMLSyntaxError as e:
                logger.error(f"Failed to parse response XML: {e}")
                return last_result
        except Exception as e:
            logger.error(f"Error extracting response: {e}")
            return "Error extracting response."

    async def _notify_observers(self, event: object) -> None:
        """Notify all subscribed observers of an event."""
        try:
            await asyncio.gather(
                *(observer(event) for observer, types in self._observers if event.event_type in types),
                return_exceptions=True
            )
        except Exception as e:
            logger.error(f"Error notifying observers: {e}")