from rich.console import Console
from rich.panel import Panel

from quantalogic_codeact.version import get_version


def get_welcome_message(agent_name: str, mode: str) -> str:
    """Generate the welcome message for the shell.
    
    Args:
        agent_name: Name of the current agent
        mode: Current agent mode ('codeact' or 'chat')
    
    Returns:
        Formatted welcome message string
    """
    return (
        f"Welcome to Quantalogic Shell (v{get_version()}).\n\n"
        f"Interacting with agent: {agent_name or 'Agent'}\n"
        f"Mode: {mode} - plain messages are "
        f"{'tasks to solve' if mode == 'codeact' else 'chat messages'}.\n\n"
        f"Type /help for commands. Press Enter to send, Ctrl+J for new lines."
    )


def print_welcome_banner(agent_name: str, mode: str, high_contrast: bool = False) -> None:
    """Print the welcome banner to the console.
    
    Args:
        agent_name: Name of the current agent
        mode: Current agent mode ('codeact' or 'chat')
        high_contrast: Whether to use high contrast colors
    """
    console = Console()
    welcome_message = get_welcome_message(agent_name, mode)
    border_style = "bright_blue" if high_contrast else "blue"
    console.print(Panel(welcome_message, title="Quantalogic Shell", border_style=border_style))
