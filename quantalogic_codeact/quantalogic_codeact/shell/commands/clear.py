from typing import List


async def clear_command(shell, args: List[str]) -> str:
    """Handle the /clear command."""
    shell.history_manager.clear_history()
    return "Conversation history cleared."