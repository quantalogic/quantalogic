from typing import List


async def contrast_command(shell, args: List[str]) -> str:
    """Toggle high-contrast mode for accessibility."""
    if not args:
        return f"High-contrast mode is {'on' if shell.high_contrast else 'off'}"
    arg = args[0].lower()
    if arg in ["on", "true", "1"]:
        shell.high_contrast = True
        return "High-contrast mode enabled."
    elif arg in ["off", "false", "0"]:
        shell.high_contrast = False
        return "High-contrast mode disabled."
    return "Invalid argument. Use /contrast on|off"