from pathlib import Path
from typing import List

import yaml
from jinja2 import Environment
from loguru import logger


async def config_save(shell, args: List[str]) -> str:
    """Save the current configuration to a file."""
    if not args:
        # No filename provided: save to default config file in user home
        config_path = Path.home() / '.quantalogic' / 'config.yaml'
        config_path.parent.mkdir(parents=True, exist_ok=True)
        filename = str(config_path)
    else:
        filename = args[0]
    config = shell.current_agent.config
    config_dict = {k: v for k, v in vars(config).items() if not k.startswith('_')}
    # Remove Jinja environment (non-serializable)
    config_dict.pop('jinja_env', None)
    # Sanitize values for YAML serialization
    def sanitize(val):
        if isinstance(val, (str, int, float, bool, type(None))):
            return val
        if isinstance(val, Environment):
            return "<jinja2.Environment>"
        if isinstance(val, dict):
            return {sanitize(k): sanitize(v) for k, v in val.items()}
        if isinstance(val, (list, tuple)):
            return [sanitize(v) for v in val]
        return repr(val)
    sanitized_config = {k: sanitize(v) for k, v in config_dict.items()}
    try:
        with open(filename, "w") as f:
            yaml.safe_dump(sanitized_config, f, default_flow_style=False)
        logger.info(f"Configuration saved to {filename}")
        return f"Configuration saved to {filename}"
    except Exception as e:
        logger.error(f"Error saving configuration to {filename}: {e}")
        return f"Error saving configuration: {e}"