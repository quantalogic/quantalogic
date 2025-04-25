from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.style import Style
from rich.text import Text

from quantalogic_codeact.version import get_version

QUANTA_LOGO = """
  ██████  ██    ██  █████  ███    ██ ████████  █████     ██       ███████   ██████  ██  ██████ 
 ██    ██ ██    ██ ██   ██ ████   ██    ██    ██   ██    ██      ██     ██ ██       ██ ██      
 ██    ██ ██    ██ ███████ ██ ██  ██    ██    ███████    ██      ██     ██ ██   ███ ██ ██      
 ██ ▄▄ ██ ██    ██ ██   ██ ██  ██ ██    ██    ██   ██    ██      ██     ██ ██    ██ ██ ██      
  ██████   ██████  ██   ██ ██   ████    ██    ██   ██    ███████  ███████   ██████  ██  ██████ 
                                                                                                
"""

def get_welcome_message(agent_name: str, mode: str) -> str:
    """Generate the welcome message for the shell.
    
    Args:
        agent_name: Name of the current agent
        mode: Current agent mode ('codeact' or 'chat')
    
    Returns:
        Formatted welcome message string
    """
    return (
        f"[bright_cyan]{QUANTA_LOGO}[/]\n"
        f"[bright_cyan]v{get_version()}[/]\n\n"
        f"[bright_green]» QUANTUM AGENT:[/] [bright_yellow]{agent_name or 'QUANTA'}[/]\n"
        f"[bright_green]» QUANTUM MODE:[/] [bright_yellow]{mode.upper()}[/] - "
        f"{'[bright_white]QUANTUM CODE SYNTHESIS[/]' if mode == 'codeact' else '[bright_white]QUANTUM CHAT PROTOCOL[/]'}\n\n"
        f"[bright_cyan]»»[/] TYPE [bright_white]/help[/] FOR QUANTUM COMMANDS\n"
        f"[bright_cyan]»»[/] PRESS [bright_white]ENTER[/] TO EXECUTE"
    )


def print_welcome_banner(agent_name: str, mode: str, high_contrast: bool = False) -> None:
    """Print the welcome banner to the console.
    
    Args:
        agent_name: Name of the current agent
        mode: Current agent mode ('codeact' or 'chat')
        high_contrast: Whether to use high contrast colors
    """
    console = Console()
    welcome_message = Text.from_markup(get_welcome_message(agent_name, mode))
    
    border_style = Style(color="bright_blue" if high_contrast else "blue", bold=True)
    
    console.print(
        Panel(
            welcome_message,
            title="[bright_white]»»—— QUANTALOGIC QUANTUM SYSTEM ——««[/]",
            title_align="center",
            border_style=border_style,
            box=ROUNDED,
            style="dim",
            padding=(1, 4),
            subtitle="[bright_cyan]QUANTUM INTELLIGENCE READY[/]"
        )
    )
