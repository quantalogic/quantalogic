import sys
from typing import List

from loguru import logger


async def loglevel_command(shell, args: List[str]) -> str:
    """Handle the /loglevel command to set or show the log level."""
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if not args:
        return f"Current log level: {shell.log_level}"
    
    level = args[0].upper()
    if level not in valid_levels:
        return "Invalid log level. Use /loglevel DEBUG|INFO|WARNING|ERROR|CRITICAL"
    
    logger.remove(shell.logger_sink_id)
    shell.logger_sink_id = logger.add(sys.stderr, level=level)
    shell.log_level = level
    return f"Log level set to {level}"