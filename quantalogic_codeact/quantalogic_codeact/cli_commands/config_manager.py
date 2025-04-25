"""
Configuration manager module. Re-exports the core functions from config_functions
to maintain backward compatibility.
"""

# Import and re-export the config constants and functions
from quantalogic_codeact.cli_commands.config_constants import GLOBAL_CONFIG_PATH, GLOBAL_DEFAULTS, PROJECT_CONFIG_PATH
from quantalogic_codeact.cli_commands.config_functions import (
    load_global_config,
    load_project_config,
    save_global_config,
    save_project_config,
)


# Add initialization hook to ensure configs are properly initialized
def ensure_config_initialized(config):
    """Ensure that the config object has required fields initialized properly."""
    if hasattr(config, 'enabled_toolboxes') and config.enabled_toolboxes is None:
        config.enabled_toolboxes = []
    return config

# Define what symbols are exported when using 'from config_manager import *'
__all__ = [
    'GLOBAL_CONFIG_PATH', 'GLOBAL_DEFAULTS', 'PROJECT_CONFIG_PATH',
    'load_global_config', 'save_global_config', 'load_project_config', 'save_project_config',
    'ensure_config_initialized'
]