"""Mode command implementation."""
from typing import List

async def mode_command(shell, args: List[str]) -> str:
    """Handle the /mode command."""
    if not args:
        return f"Current mode: {shell.mode}"
    
    mode = args[0].lower()
    if mode in ["codeact", "react"]:
        shell.mode = mode
        return f"Mode set to {mode}"
    else:
        return "Invalid mode. Use /mode codeact|react"
