import sys
from typing import List

from loguru import logger


async def debug_command(shell, args: List[str]) -> str:
    """Toggle debug mode for detailed error logging."""
    if not args:
        return f"Debug mode is {'on' if shell.debug else 'off'}"
    arg = args[0].lower()
    if arg in ["on", "true", "1"]:
        shell.debug = True
        logger.remove(shell.logger_sink_id)
        shell.logger_sink_id = logger.add(sys.stderr, level="DEBUG")
        return "Debug mode enabled."
    elif arg in ["off", "false", "0"]:
        shell.debug = False
        logger.remove(shell.logger_sink_id)
        shell.logger_sink_id = logger.add(sys.stderr, level="INFO")
        return "Debug mode disabled."
    return "Invalid argument. Use /debug on|off"