from pathlib import Path

import yaml

# Centralized global config
GLOBAL_CONFIG_PATH = Path.home() / ".quantalogic/config.yaml"
GLOBAL_DEFAULTS = {"installed_toolboxes": [], "enabled_toolboxes": []}

def load_global_config() -> dict:
    """Load or initialize global config."""
    if GLOBAL_CONFIG_PATH.exists():
        try:
            data = yaml.safe_load(GLOBAL_CONFIG_PATH.read_text()) or {}
            return {**GLOBAL_DEFAULTS, **data}
        except Exception:
            return GLOBAL_DEFAULTS.copy()
    return GLOBAL_DEFAULTS.copy()

def save_global_config(config: dict) -> None:
    """Save global config."""
    GLOBAL_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    GLOBAL_CONFIG_PATH.write_text(yaml.safe_dump(config, default_flow_style=False))
