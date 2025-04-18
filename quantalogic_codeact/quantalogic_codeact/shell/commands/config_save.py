from typing import List

import yaml
from loguru import logger


async def config_save(shell, args: List[str]) -> str:
    """Save the current configuration to a file."""
    if not args:
        return "Please provide a filename. Usage: /config save [filename]"
    filename = args[0]
    config = shell.current_agent.config
    config_dict = {k: v for k, v in vars(config).items() if not k.startswith('_')}
    try:
        with open(filename, "w") as f:
            yaml.safe_dump(config_dict, f, default_flow_style=False)
        logger.info(f"Configuration saved to {filename}")
        return f"Configuration saved to {filename}"
    except Exception as e:
        logger.error(f"Error saving configuration to {filename}: {e}")
        return f"Error saving configuration: {e}"