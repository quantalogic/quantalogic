"""High-level interface for the Quantalogic Agent with modular configuration."""

from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

import yaml
from loguru import logger
from pydantic import BaseModel, Field, root_validator, validator

from .constants import MAX_HISTORY_TOKENS
from .personality_config import PersonalityConfig


# Structured config models (replaced dataclasses with Pydantic BaseModel)
class ReasonerConfig(BaseModel):
    """Configuration for the reasoner component."""
    name: str = Field(default="default", description="Name of the reasoner")
    config: Dict[str, Any] = Field(default_factory=dict, description="Additional reasoner configuration")


class ExecutorConfig(BaseModel):
    """Configuration for the executor component."""
    name: str = Field(default="default", description="Name of the executor")
    config: Dict[str, Any] = Field(default_factory=dict, description="Additional executor configuration")


# PersonalityConfig is now imported from personality_config.py


class TemplateConfig(BaseModel):
    """Configuration for templating engine: directory for templates."""
    template_dir: Optional[Path] = Field(None, description="Directory for Jinja2 templates")


class Toolbox(BaseModel):
    """Represents a single installed toolbox."""
    name: str = Field(..., description="Name of the toolbox")
    package: str = Field(..., description="Package name in PyPI or local path")
    version: str = Field(..., description="Version of the toolbox")
    path: Optional[str] = Field(None, description="Filesystem path to the toolbox module")
    enabled: bool = Field(default=True, description="Whether the toolbox is enabled")
    tool_configs: List["ToolConfig"] = Field(default_factory=list, description="Per-tool configuration for this toolbox")


class ToolConfig(BaseModel):
    """Represents configuration for a specific tool within a toolbox."""
    name: str = Field(..., description="Name of the tool")
    enabled: bool = Field(True, description="Whether the tool is enabled")
    config: Dict[str, Any] = Field(default_factory=dict, description="Additional tool configuration")


# Resolve forward references for Toolbox
Toolbox.update_forward_refs()


# Module-level constants
GLOBAL_CONFIG_PATH = Path.home() / ".quantalogic" / "config.json"
GLOBAL_DEFAULTS = {
    "log_level": "ERROR",
    "model": "gemini/gemini-2.0-flash",
    "version": "1.0.0"
}

class AgentConfig(BaseModel):
    """Comprehensive configuration for the Agent, loadable from a YAML file or direct arguments."""
    GLOBAL_CONFIG_PATH: ClassVar[Path] = GLOBAL_CONFIG_PATH
    GLOBAL_DEFAULTS: ClassVar[dict] = GLOBAL_DEFAULTS

    version: str = Field(default="1.0", description="Configuration schema version")
    model: str = Field(default="gemini/gemini-2.0-flash", description="The LLM model to use")
    max_iterations: int = Field(default=5, ge=1, le=100, description="Maximum reasoning steps")
    max_history_tokens: int = Field(default=MAX_HISTORY_TOKENS, ge=1000, description="Max tokens for history")
    installed_toolboxes: List[Toolbox] = Field(default_factory=list, description="List of installed toolboxes")
    reasoner_name: str = Field(default="default", description="Name of the reasoner")
    executor_name: str = Field(default="default", description="Name of the executor")
    personality: PersonalityConfig = Field(default_factory=PersonalityConfig, description="Comprehensive agent personality configuration")
    template: TemplateConfig = Field(default_factory=TemplateConfig)
    name: Optional[str] = Field(None, description="Agent name")
    reasoner: ReasonerConfig = Field(default_factory=lambda: ReasonerConfig(name="default"))
    executor: ExecutorConfig = Field(default_factory=lambda: ExecutorConfig(name="default"))
    agent_tool_model: str = Field(default="gemini/gemini-2.0-flash", description="Model for agent tool")
    agent_tool_timeout: int = Field(default=30, ge=1, description="Timeout for agent tool")
    temperature: float = Field(default=0.7, ge=0.0, le=1.0, description="Temperature for LLM generation")
    mode: str = Field(default="codeact", description="Operating mode: 'codeact' or 'chat'")
    streaming: bool = Field(default=True, description="Enable streaming output for real-time token generation")
    log_level: str = Field(default="ERROR", description="Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL")

    @classmethod
    def ensure_initialized(cls, config):
        """Ensure all required fields exist in the config."""
        for key, value in cls.GLOBAL_DEFAULTS.items():
            if not hasattr(config, key):
                setattr(config, key, value)
        return config

    @classmethod
    def create_default_if_missing(cls):
        """Create default config file if it doesn't exist."""
        path = Path(cls.GLOBAL_CONFIG_PATH)
        if not path.exists():
            config = cls()
            for key, value in cls.GLOBAL_DEFAULTS.items():
                setattr(config, key, value)
            config.save_to_file(str(path))

    @root_validator(pre=True)
    def migrate_enabled_toolboxes(cls, values):
        """Migrate legacy enabled_toolboxes to enabled field in installed_toolboxes."""
        enabled_toolboxes = values.pop("enabled_toolboxes", [])  # Remove legacy field
        installed_toolboxes = values.get("installed_toolboxes", [])
        if enabled_toolboxes and installed_toolboxes:
            for tb in installed_toolboxes:
                if isinstance(tb, dict):
                    tb["enabled"] = tb.get("name", "") in enabled_toolboxes
                elif isinstance(tb, Toolbox):
                    tb.enabled = tb.name in enabled_toolboxes
        return values

    @property
    def enabled_toolboxes(self) -> List[str]:
        """Return list of enabled toolbox names for compatibility."""
        return [tb.name for tb in self.installed_toolboxes if tb.enabled]

    @validator("model")
    def validate_model(cls, v):
        if not v:
            raise ValueError("Model must be specified")
        return v

    @validator("reasoner", pre=True)
    def validate_reasoner(cls, v):
        """Convert reasoner dict to ReasonerConfig."""
        if isinstance(v, dict):
            return ReasonerConfig(**v)
        elif isinstance(v, ReasonerConfig):
            return v
        raise ValueError("reasoner must be a dict or ReasonerConfig")

    @validator("executor", pre=True)
    def validate_executor(cls, v):
        """Convert executor dict to ExecutorConfig."""
        if isinstance(v, dict):
            return ExecutorConfig(**v)
        elif isinstance(v, ExecutorConfig):
            return v
        raise ValueError("executor must be a dict or ExecutorConfig")

    @validator("personality", pre=True)
    def validate_personality(cls, v):
        """Ensure personality is a PersonalityConfig instance."""
        if isinstance(v, PersonalityConfig):
            return v
        elif isinstance(v, dict):
            return PersonalityConfig(**v)
        elif v is None:
            return PersonalityConfig()
        else:
            logger.warning(f"Unexpected personality type {type(v)}: {v}. Falling back to empty PersonalityConfig.")
            return PersonalityConfig()

    @validator("installed_toolboxes", pre=True)
    def validate_installed_toolboxes(cls, v):
        """Convert installed_toolboxes to list of Toolbox."""
        if v is None:
            return []
        return [tb if isinstance(tb, Toolbox) else Toolbox(**tb) for tb in v]

    @validator("template", pre=True)
    def validate_template(cls, v):
        """Convert template dict to TemplateConfig."""
        if isinstance(v, dict):
            return TemplateConfig(**v)
        elif isinstance(v, TemplateConfig):
            return v
        return TemplateConfig()

    @validator("mode")
    def validate_mode(cls, v):
        """Ensure mode is either 'codeact' or 'chat'."""
        if v not in ["codeact", "chat"]:
            raise ValueError("mode must be 'codeact' or 'chat'")
        return v

    @validator("log_level")
    def validate_log_level(cls, v):
        """Ensure log_level is valid."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {', '.join(valid_levels)}")
        return v.upper()

    @classmethod
    def get_default(cls) -> "AgentConfig":
        """Return a default AgentConfig instance with all default values."""
        return cls()

    @classmethod
    def load_from_file(cls, path: str) -> "AgentConfig":
        """Load configuration from a YAML file."""
        try:
            config_path = Path(path).expanduser().resolve()
            if not config_path.exists():
                # Create the config file with default settings if it doesn't exist
                logger.info(f"Config file {path} not found. Creating with default settings.")
                config = cls()  # Create default config
                try:
                    config_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(config_path, "w") as f:
                        yaml.safe_dump(config.dict(), f, default_flow_style=False)
                    logger.info(f"Created default config file at {config_path}")
                    return config
                except Exception as create_err:
                    logger.error(f"Failed to create default config file: {create_err}")
                    return config
            
            # File exists, load it
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
            return cls(**data)
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML config {path}: {e}. Using defaults.")
            return cls()
        except Exception as e:
            logger.error(f"Failed to load config from {path}: {e}")
            return cls()

    def save_to_file(self, path: str) -> None:
        """Save configuration to a YAML file."""
        try:
            config_path = Path(path).expanduser().resolve()
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w") as f:
                yaml.safe_dump(self.dict(), f, default_flow_style=False)
        except Exception as e:
            logger.error(f"Failed to save config to {path}: {e}")
            raise

    def to_dict(self) -> Dict[str, Any]:
        """Convert the AgentConfig instance into a dictionary suitable for saving."""
        return self.dict()