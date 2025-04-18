from typing import List

from rich.console import Console
from rich.panel import Panel

console = Console()

async def tutorial_command(shell, args: List[str]) -> str:
    """Display a tutorial for new users."""
    tutorial = (
        "Welcome to Quantalogic Shell!\n\n"
        "1. Type messages to chat (react mode) or solve tasks (codeact mode).\n"
        "2. Use /mode [react|codeact] to switch modes.\n"
        "3. Commands start with '/': try /help, /chat, /solve.\n"
        "4. Press Enter to send, Ctrl+J for new lines.\n"
        "5. Use /history to see past messages.\n"
        "6. Type /exit to quit."
    )
    border_color = "bright_blue" if shell.high_contrast else "blue"
    console.print(Panel(tutorial, title="Tutorial", border_style=border_color))
    return ""