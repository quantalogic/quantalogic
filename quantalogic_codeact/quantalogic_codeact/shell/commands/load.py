import json
from typing import List

from loguru import logger


async def load_command(shell, args: List[str]) -> str:
    """Load conversation history from a file."""
    if not args:
        return "Please provide a filename."
    filename = args[0]
    try:
        with open(filename) as f:
            history = json.load(f)
        shell.conversation_manager.messages = history
        shell.conversation_manager.message_dict = {m['nanoid']: m for m in history}
        return f"History loaded from {filename}"
    except Exception as e:
        if shell.debug:
            logger.exception("Load error")
        return f"Error loading history: {e}"