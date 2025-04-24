"""
Configuration functions that can be imported directly by other modules.
This module is structured to avoid circular imports by deferring imports of AgentConfig.
"""
from loguru import logger

# Import constants directly, these won't cause circular imports
from quantalogic_codeact.cli_commands.config_constants import GLOBAL_CONFIG_PATH, GLOBAL_DEFAULTS

# Import the low-level utilities that don't depend on AgentConfig
from quantalogic_codeact.cli_commands.config_utils import load_yaml_config, save_yaml_config


def load_global_config():
    """Load or initialize global config as an AgentConfig, using defaults when loaded values are None."""
    # Lazy import to avoid circular dependencies
    from quantalogic_codeact.codeact.agent_config import AgentConfig
    
    # Use the low-level utility to load the YAML data
    config_data = load_yaml_config(GLOBAL_CONFIG_PATH)
    
    # If the file was empty or not found, use defaults
    if not config_data:
        return AgentConfig(**GLOBAL_DEFAULTS)
        
    # Create AgentConfig from the loaded data
    try:
        return AgentConfig(**config_data)
    except Exception as e:
        logger.error(f"Failed to create AgentConfig from data: {e}. Using defaults.")
        return AgentConfig(**GLOBAL_DEFAULTS)


def save_global_config(config):
    """Save global config atomically, ensuring models are serialized correctly."""
    try:
        # Convert to dictionary for saving
        if hasattr(config, 'dict'):
            config_dict = config.dict(exclude={"config_file"})
        elif hasattr(config, 'to_dict'):
            config_dict = config.to_dict()
        else:
            config_dict = dict(config)
            
        # Use the low-level utility to save the config
        save_yaml_config(GLOBAL_CONFIG_PATH, config_dict)
    except Exception as e:
        logger.error(f"Failed to save config to {GLOBAL_CONFIG_PATH}: {e}")
        raise


def load_project_config():
    """Load or initialize project config using global config."""
    return load_global_config()


def save_project_config(config):
    """Save project config using global config."""
    save_global_config(config)
