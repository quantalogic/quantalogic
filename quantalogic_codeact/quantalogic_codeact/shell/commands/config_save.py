from pathlib import Path
from typing import List

from loguru import logger

import quantalogic_codeact.cli_commands.config_manager as config_manager


async def config_save(shell, args: List[str]) -> str:
    """Save the current configuration to a file."""
    # Determine save path: use provided filename or default global config
    path = Path(args[0]).expanduser().resolve() if args else config_manager.GLOBAL_CONFIG_PATH.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    filename = str(path)
    try:
        shell.agent_config.save_to_file(filename)
        logger.info(f"Configuration saved to {filename}")
        # Track this path for future operations
        config_manager.GLOBAL_CONFIG_PATH = path
        config_manager.PROJECT_CONFIG_PATH = path
        return f"Configuration saved to {filename}"
    except Exception as e:
        logger.error(f"Error saving configuration to {filename}: {e}")
        return f"Error saving configuration: {e}"
