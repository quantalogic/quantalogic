from pathlib import Path
import yaml

# Centralized global config
GLOBAL_CONFIG_PATH = Path.home() / ".quantalogic/config.yaml"
GLOBAL_DEFAULTS = {"installed_toolboxes": [], "enabled_toolboxes": [], "log_level": "ERROR"}

# Project-level config now uses global config
PROJECT_CONFIG_PATH = GLOBAL_CONFIG_PATH

def load_global_config() -> dict:
    """Load or initialize global config, using defaults when loaded values are None."""
    if GLOBAL_CONFIG_PATH.exists():
        try:
            data = yaml.safe_load(GLOBAL_CONFIG_PATH.read_text()) or {}
            config = GLOBAL_DEFAULTS.copy()
            for key, value in data.items():
                if value is not None:
                    config[key] = value
            return config
        except Exception:
            return GLOBAL_DEFAULTS.copy()
    return GLOBAL_DEFAULTS.copy()

def save_global_config(config: dict) -> None:
    """Save global config."""
    GLOBAL_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    GLOBAL_CONFIG_PATH.write_text(yaml.safe_dump(config, default_flow_style=False))

def load_project_config() -> dict:
    """Load or initialize project config using global config."""
    return load_global_config()

def save_project_config(config: dict) -> None:
    """Save project config using global config."""
    save_global_config(config)
