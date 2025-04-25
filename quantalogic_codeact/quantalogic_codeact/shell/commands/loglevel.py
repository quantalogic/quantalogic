import sys
from typing import List

from loguru import logger
from rich.console import Console

console = Console()


async def loglevel_command(shell, args: List[str]) -> str:
    """Set log level: /loglevel [DEBUG|INFO|WARNING|ERROR|CRITICAL]"""
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if not args:
        return f"Current log level: {shell.agent_config.log_level}"
    
    level = args[0].upper()
    if level not in valid_levels:
        return f"Invalid log level. Use one of: {', '.join(valid_levels)}"
    
    try:
        # Store the current handler ID
        old_handler_id = getattr(shell, 'logger_sink_id', None)
        
        # Add new logger handler
        new_handler_id = logger.add(
            sys.stderr,
            level=level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
                   "<cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
        )
        
        # Remove the old handler if it exists
        if old_handler_id is not None:
            try:
                logger.remove(old_handler_id)
            except ValueError as e:
                logger.warning(f"Could not remove old handler {old_handler_id}: {e}")
        
        # Update shell with new handler ID and log level
        shell.logger_sink_id = new_handler_id
        shell.agent_config.log_level = level
        shell.log_level = level
        
        return f"Log level set to {level}"
    except Exception as e:
        console.print(f"[red]Error setting log level: {e}[/red]")
        return f"Error setting log level: {e}"
