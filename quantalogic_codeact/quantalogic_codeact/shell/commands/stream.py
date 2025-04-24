from typing import List


async def stream_command(shell, args: List[str]) -> str:
    """Handle the /stream command."""
    if not args:
        return f"Streaming is {'on' if shell.agent_config.streaming else 'off'}"
    
    arg = args[0].lower()
    if arg in ["on", "true", "1"]:
        shell.agent_config.streaming = True
        return "Streaming enabled."
    elif arg in ["off", "false", "0"]:
        shell.agent_config.streaming = False
        return "Streaming disabled."
    else:
        return "Invalid argument. Use /stream on|off"