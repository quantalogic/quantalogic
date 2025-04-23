"""High-level interface for the Quantalogic Agent with modular configuration."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import yaml
from loguru import logger

from quantalogic.tools import Tool

from .constants import MAX_HISTORY_TOKENS


# Structured config dataclasses
@dataclass
class ReasonerConfig:
    name: str = "default"
    config: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ExecutorConfig:
    name: str = "default"
    config: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PersonalityConfig:
    traits: List[str] = field(default_factory=list)

@dataclass
class ToolConfig:
    name: str
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TemplateConfig:
    """Configuration for templating engine: directory for templates."""
    template_dir: Optional[Path] = None

@dataclass
class AgentConfig:
    """Comprehensive configuration for the Agent, loadable from a YAML file or direct arguments."""
    model: str = "gemini/gemini-2.0-flash"
    max_iterations: int = 5
    tools: Optional[List[Union[Tool, Callable]]] = None
    max_history_tokens: int = MAX_HISTORY_TOKENS
    toolbox_directory: str = "toolboxes"
    enabled_toolboxes: Optional[List[str]] = None
    installed_toolboxes: Optional[List[Dict[str, Any]]] = None
    reasoner_name: str = "default"
    executor_name: str = "default"
    personality: Optional[str] = None
    backstory: Optional[str] = None
    sop: Optional[str] = None
    template: TemplateConfig = field(default_factory=TemplateConfig)
    name: Optional[str] = None
    tools_config: Optional[List[Dict[str, Any]]] = None
    reasoner: Optional[Dict[str, Any]] = field(default_factory=lambda: {"name": "default"})
    executor: Optional[Dict[str, Any]] = field(default_factory=lambda: {"name": "default"})
    agent_tool_model: str = "gemini/gemini-2.0-flash"
    agent_tool_timeout: int = 30
    temperature: float = 0.7  # Added temperature field
    system_prompt_template: Optional[str] = None

    def __init__(
        self,
        model: str = "gemini/gemini-2.0-flash",
        max_iterations: int = 5,
        tools: Optional[List[Union[Tool, Callable]]] = None,
        max_history_tokens: int = MAX_HISTORY_TOKENS,
        toolbox_directory: str = "toolboxes",
        enabled_toolboxes: Optional[List[str]] = None,
        installed_toolboxes: Optional[List[Dict[str, Any]]] = None,
        reasoner_name: str = "default",
        executor_name: str = "default",
        personality: Optional[str] = None,
        backstory: Optional[str] = None,
        sop: Optional[str] = None,
        template: Optional[TemplateConfig] = None,
        config_file: Optional[str] = None,
        name: Optional[str] = None,
        tools_config: Optional[List[Dict[str, Any]]] = None,
        reasoner: Optional[Dict[str, Any]] = None,
        executor: Optional[Dict[str, Any]] = None,
        agent_tool_model: str = "gemini/gemini-2.0-flash",
        agent_tool_timeout: int = 30,
        temperature: float = 0.7,  # Added temperature parameter
        system_prompt_template: Optional[str] = None
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
                                          tools, enabled_toolboxes, installed_toolboxes, reasoner_name, executor_name, personality,
                                          backstory, sop, template, name, tools_config, reasoner, executor,
                                          agent_tool_model, agent_tool_timeout, temperature, system_prompt_template)
                except FileNotFoundError as e:
                    logger.warning(f"Config file {config_path} not found: {e}. No toolboxes will be loaded.")
                    self._set_defaults(model, max_iterations, max_history_tokens, toolbox_directory,
                                      tools, enabled_toolboxes, installed_toolboxes, reasoner_name, executor_name, personality,
                                      backstory, sop, template, name, tools_config, reasoner, executor,
                                      agent_tool_model, agent_tool_timeout, temperature, system_prompt_template)
                except yaml.YAMLError as e:
                    logger.error(f"Error parsing YAML config {config_path}: {e}. No toolboxes will be loaded.")
                    self._set_defaults(model, max_iterations, max_history_tokens, toolbox_directory,
                                      tools, enabled_toolboxes, installed_toolboxes, reasoner_name, executor_name, personality,
                                      backstory, sop, template, name, tools_config, reasoner, executor,
                                      agent_tool_model, agent_tool_timeout, temperature, system_prompt_template)
            else:
                self._set_defaults(model, max_iterations, max_history_tokens, toolbox_directory,
                                  tools, enabled_toolboxes, installed_toolboxes, reasoner_name, executor_name, personality,
                                  backstory, sop, template, name, tools_config, reasoner, executor,
                                  agent_tool_model, agent_tool_timeout, temperature, system_prompt_template)
        except Exception as e:
            logger.error(f"Failed to initialize AgentConfig: {e}")
            raise

    def _load_from_config(self, config: Dict, *args) -> None:
        """Load configuration from a dictionary, overriding with explicit arguments if provided."""
        try:
            model, max_iterations, max_history_tokens, toolbox_directory, tools, enabled_toolboxes, installed_toolboxes, \
            reasoner_name, executor_name, personality, backstory, sop, template, name, tools_config, \
            reasoner, executor, agent_tool_model, agent_tool_timeout, temperature, system_prompt_template = args
            
            self.model = config.get("model", model)
            self.max_iterations = config.get("max_iterations", max_iterations)
            self.max_history_tokens = config.get("max_history_tokens", max_history_tokens)
            self.toolbox_directory = config.get("toolbox_directory", toolbox_directory)
            self.tools = tools if tools is not None else config.get("tools")
            # Treat empty list as no filter (i.e., include all toolboxes)
            etb = config.get("enabled_toolboxes", enabled_toolboxes)
            self.enabled_toolboxes = etb if etb else None
            self.installed_toolboxes = config.get("installed_toolboxes", installed_toolboxes)
            rd = config.get("reasoner", {})
            self.reasoner = ReasonerConfig(
                name=rd.get("name", reasoner_name),
                config=rd.get("config", {})
            )
            ed = config.get("executor", {})
            self.executor = ExecutorConfig(
                name=ed.get("name", executor_name),
                config=ed.get("config", {})
            )
            pd = config.get("personality", {}) or {}
            self.personality = PersonalityConfig(traits=pd.get("traits", []))
            self.tools_config = [ToolConfig(**tc) for tc in config.get("tools_config", tools_config or [])]
            # Load template config from YAML if present, else use passed TemplateConfig or default
            tpl_cfg = config.get("template")
            if isinstance(tpl_cfg, dict):
                td = tpl_cfg.get("template_dir")
                self.template = TemplateConfig(template_dir=Path(td) if td else None)
            elif template is not None:
                self.template = template
            else:
                self.template = TemplateConfig()
            self.name = config.get("name", name)
            self.agent_tool_model = config.get("agent_tool_model", agent_tool_model)
            self.agent_tool_timeout = config.get("agent_tool_timeout", agent_tool_timeout)
            self.temperature = config.get("temperature", temperature)  # Added temperature
            self.system_prompt_template = config.get("system_prompt_template", system_prompt_template)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            raise

    def _set_defaults(self, model, max_iterations, max_history_tokens, toolbox_directory,
                     tools, enabled_toolboxes, installed_toolboxes, reasoner_name, executor_name, personality,
                     backstory, sop, template, name, tools_config, reasoner, executor,
                     agent_tool_model, agent_tool_timeout, temperature, system_prompt_template) -> None:
        """Set default values for all configuration fields."""
        try:
            self.model = model
            self.max_iterations = max_iterations
            self.max_history_tokens = max_history_tokens
            self.toolbox_directory = toolbox_directory
            self.tools = tools
            self.enabled_toolboxes = enabled_toolboxes
            self.installed_toolboxes = installed_toolboxes
            if isinstance(reasoner, dict):
                self.reasoner = ReasonerConfig(
                    name=reasoner.get("name", reasoner_name),
                    config=reasoner.get("config", {})
                )
            else:
                self.reasoner = reasoner if isinstance(reasoner, ReasonerConfig) else ReasonerConfig(name=reasoner_name)
            if isinstance(executor, dict):
                self.executor = ExecutorConfig(
                    name=executor.get("name", executor_name),
                    config=executor.get("config", {})
                )
            else:
                self.executor = executor if isinstance(executor, ExecutorConfig) else ExecutorConfig(name=executor_name)
            # Support various personality formats
            if isinstance(personality, PersonalityConfig):
                self.personality = personality
            elif isinstance(personality, dict):
                self.personality = PersonalityConfig(traits=personality.get("traits", []))
            elif isinstance(personality, list):
                self.personality = PersonalityConfig(traits=personality)
            elif isinstance(personality, str):
                self.personality = personality
            else:
                self.personality = PersonalityConfig()
            self.tools_config = [tc if isinstance(tc, ToolConfig) else ToolConfig(**tc) for tc in (tools_config or [])]
            self.template = template if template is not None else TemplateConfig()
            self.name = name
            self.agent_tool_model = agent_tool_model
            self.agent_tool_timeout = agent_tool_timeout
            self.temperature = temperature  # Added temperature
            self.system_prompt_template = system_prompt_template
        except Exception as e:
            logger.error(f"Error setting defaults: {e}")
            raise