"""
Low-level configuration utilities that don't have any dependencies
on other modules in the project to avoid circular imports.
"""
import os
import tempfile
from pathlib import Path

import yaml
from loguru import logger


def load_yaml_config(path: Path) -> dict:
    """Load a YAML configuration file and return as a dictionary.
    
    This is a low-level function that doesn't know about AgentConfig.
    """
    if path.exists():
        try:
            with open(path) as f:
                config_data = yaml.safe_load(f) or {}
                # Ensure enabled_toolboxes is a list even if found in the config
                if 'enabled_toolboxes' in config_data and config_data['enabled_toolboxes'] is None:
                    config_data['enabled_toolboxes'] = []
                return config_data
        except Exception as e:
            logger.error(f"Failed to load config from {path}: {e}. Using defaults.")
    return {}

def save_yaml_config(path: Path, config_dict: dict) -> None:
    """Save a dictionary as YAML configuration.
    
    This is a low-level function that doesn't know about AgentConfig.
    """
    try:
        # Write to a temporary file first
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', delete=False, dir=path.parent, suffix='.yaml') as temp_file:
            yaml.safe_dump(config_dict, temp_file, default_flow_style=False)
            temp_file_path = temp_file.name
        
        # Atomically replace the config file
        os.replace(temp_file_path, path)
        logger.info(f"Successfully saved config to {path}")
    except Exception as e:
        logger.error(f"Failed to save config to {path}: {e}")
        if 'temp_file_path' in locals():
            try:
                os.remove(temp_file_path)
            except Exception:
                pass
        raise
