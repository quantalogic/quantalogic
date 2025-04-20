from pathlib import Path
import quantalogic_codeact.codeact.cli_commands.config_manager as config_manager
from typing import List

import yaml
from jinja2 import Environment
from loguru import logger


async def config_save(shell, args: List[str]) -> str:
    """Save the current configuration to a file."""
    # Determine save path: use provided filename or default global config
    if not args:
        path = config_manager.GLOBAL_CONFIG_PATH.expanduser().resolve()
    else:
        path = Path(args[0]).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    filename = str(path)
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
        # Track this path for future operations
        config_manager.GLOBAL_CONFIG_PATH = path
        config_manager.PROJECT_CONFIG_PATH = path
        return f"Configuration saved to {filename}"
    except Exception as e:
        logger.error(f"Error saving configuration to {filename}: {e}")
        return f"Error saving configuration: {e}"