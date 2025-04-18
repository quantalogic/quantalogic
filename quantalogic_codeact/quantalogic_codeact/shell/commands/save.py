import json
from typing import List

from loguru import logger


async def save_command(shell, args: List[str]) -> str:
    """Save conversation history to a file."""
    if not args:
        return "Please provide a filename."
    filename = args[0]
    try:
        with open(filename, "w") as f:
            json.dump(shell.current_message_history, f)
        return f"History saved to {filename}"
    except Exception as e:
        if shell.debug:
            logger.exception("Save error")
        return f"Error saving history: {e}"