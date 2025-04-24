"""
Constants used by configuration-related modules.
This module should not import from any other modules to avoid circular imports.
"""
from pathlib import Path

# Centralized global config
GLOBAL_CONFIG_PATH = Path.home() / ".quantalogic/config.yaml"
GLOBAL_DEFAULTS = {"installed_toolboxes": [], "log_level": "ERROR"}



# Project-level config now uses global config
PROJECT_CONFIG_PATH = GLOBAL_CONFIG_PATH