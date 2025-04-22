"""High-level interface for the Quantalogic Agent with modular configuration."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import yaml
from jinja2 import Environment
from loguru import logger

from quantalogic.tools import Tool

from .constants import MAX_HISTORY_TOKENS
from .templates import jinja_env as default_jinja_env


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
    temperature: float = 0.7  # Added temperature field

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
        agent_tool_timeout: int = 30,
        temperature: float = 0.7  # Added temperature parameter
    ) -> None:
        """Initialize configuration from arguments or a YAML file."""
        try:
            if config_file:
                config_path = Path(config_file)
                if not config_path.is_absolute():
                    config_path = Path.cwd() / config_file  # Resolve relative to current working directory
                try:
                    with open(config_path) as f:
                        config: Dict = yaml.safe_load(f) or {}
                    self._load_from_config(config, model, max_iterations, max_history_tokens, toolbox_directory,
                                          tools, enabled_toolboxes, reasoner_name, executor_name, personality,
                                          backstory, sop, jinja_env, name, tools_config, reasoner, executor,
                                          profile, customizations, agent_tool_model, agent_tool_timeout, temperature)
                except FileNotFoundError as e:
                    logger.warning(f"Config file {config_path} not found: {e}. No toolboxes will be loaded.")
                    self._set_defaults(model, max_iterations, max_history_tokens, toolbox_directory,
                                      tools, [], reasoner_name, executor_name, personality,
                                      backstory, sop, jinja_env, name, tools_config, reasoner, executor,
                                      profile, customizations, agent_tool_model, agent_tool_timeout, temperature)
                except yaml.YAMLError as e:
                    logger.error(f"Error parsing YAML config {config_path}: {e}. No toolboxes will be loaded.")
                    self._set_defaults(model, max_iterations, max_history_tokens, toolbox_directory,
                                      tools, [], reasoner_name, executor_name, personality,
                                      backstory, sop, jinja_env, name, tools_config, reasoner, executor,
                                      profile, customizations, agent_tool_model, agent_tool_timeout, temperature)
            else:
                self._set_defaults(model, max_iterations, max_history_tokens, toolbox_directory,
                                  tools, enabled_toolboxes, reasoner_name, executor_name, personality,
                                  backstory, sop, jinja_env, name, tools_config, reasoner, executor,
                                  profile, customizations, agent_tool_model, agent_tool_timeout, temperature)
            self.__post_init__()
        except Exception as e:
            logger.error(f"Failed to initialize AgentConfig: {e}")
            raise

    def _load_from_config(self, config: Dict, *args) -> None:
        """Load configuration from a dictionary, overriding with explicit arguments if provided."""
        try:
            model, max_iterations, max_history_tokens, toolbox_directory, tools, enabled_toolboxes, \
            reasoner_name, executor_name, personality, backstory, sop, jinja_env, name, tools_config, \
            reasoner, executor, profile, customizations, agent_tool_model, agent_tool_timeout, temperature = args
            
            self.model = config.get("model", model)
            self.max_iterations = config.get("max_iterations", max_iterations)
            self.max_history_tokens = config.get("max_history_tokens", max_history_tokens)
            self.toolbox_directory = config.get("toolbox_directory", toolbox_directory)
            self.tools = tools if tools is not None else config.get("tools")
            # Treat empty list as no filter (i.e., include all toolboxes)
            etb = config.get("enabled_toolboxes", enabled_toolboxes)
            self.enabled_toolboxes = etb if etb else None
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
            self.temperature = config.get("temperature", temperature)  # Added temperature
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            raise

    def _set_defaults(self, model, max_iterations, max_history_tokens, toolbox_directory,
                     tools, enabled_toolboxes, reasoner_name, executor_name, personality,
                     backstory, sop, jinja_env, name, tools_config, reasoner, executor,
                     profile, customizations, agent_tool_model, agent_tool_timeout, temperature) -> None:
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
            self.temperature = temperature  # Added temperature
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
        except Exception as e:
            logger.error(f"Error in post_init: {e}")
            raise