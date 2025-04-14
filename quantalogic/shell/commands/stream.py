"""Stream command implementation."""
from typing import List


async def stream_command(shell, args: List[str]) -> str:
    """Handle the /stream command."""
    if not args:
        return f"Streaming is {'on' if shell.streaming else 'off'}"
    
    arg = args[0].lower()
    if arg in ["on", "true", "1"]:
        shell.streaming = True
        return "Streaming enabled."
    elif arg in ["off", "false", "0"]:
        shell.streaming = False
        return "Streaming disabled."
    else:
        return "Invalid argument. Use /stream on|off"
