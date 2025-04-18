from typing import List


async def inputmode_command(shell, args: List[str]) -> str:
    """Toggle between single-line and multiline input."""
    if not args:
        return f"Input mode: {'multiline' if shell.multiline else 'single'}"
    mode = args[0].lower()
    if mode in ["single", "multi"]:
        shell.multiline = (mode == "multi")
        shell.session.multiline = shell.multiline
        return f"Input mode set to {mode}"
    return "Invalid mode. Use /inputmode single|multi"