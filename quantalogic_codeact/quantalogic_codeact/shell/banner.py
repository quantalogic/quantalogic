from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.style import Style
from rich.text import Text

from quantalogic_codeact.version import get_version

QUANTUM_SYMBOL = """
    ⟨ψ|H|ψ⟩
    |⟩⟨|
    ⊗|ψ⟩
"""

QUANTA_LOGO = """
   ██████  ██    ██   █████   ███    ██ ████████  █████      ██       ███████   ██████  ██  ██████ 
  ██    ██ ██    ██  ██   ██  ████   ██    ██    ██   ██     ██      ██     ██ ██       ██ ██      
  ██    ██ ██    ██  ███████  ██ ██  ██    ██    ███████     ██      ██     ██ ██   ███ ██ ██      
  ██ ▄▄ ██ ██    ██  ██   ██  ██  ██ ██    ██    ██   ██     ██      ██     ██ ██    ██ ██ ██      
   ██████   ██████   ██   ██  ██   ████    ██    ██   ██     ███████  ███████   ██████  ██  ██████ 
                                                                                                   
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
        f"[bright_green]» QUANTUM AGENT:[/] [bright_yellow]{agent_name or 'QUANTA'}[/] [bright_blue]⟨ψ|[/]\n"
        f"[bright_green]» QUANTUM MODE:[/] [bright_yellow]{mode.upper()}[/] [bright_blue]⊗[/] "
        f"{'[bright_white]QUANTUM CODE SYNTHESIS[/]' if mode == 'codeact' else '[bright_white]QUANTUM CHAT PROTOCOL[/]'} [bright_blue]|ψ⟩[/]\n\n"
        f"[bright_cyan]»»[/] TYPE [bright_white]/help[/] FOR QUANTUM COMMANDS [bright_blue]⟨ϕ|[/]\n"
        f"[bright_cyan]»»[/] PRESS [bright_white]ENTER[/] TO EXECUTE [bright_blue]H|ψ⟩[/]"
    )


def print_welcome_banner(agent_name: str, mode: str, high_contrast: bool = False) -> None:
    """Print the welcome banner to the console with consistent colors."""
    console = Console()
    
    # Use high contrast colors if enabled
    border_color = "bright_blue" if high_contrast else "blue"
    _text_color = "bright_white" if high_contrast else "white"
    
    welcome_message = Text.from_markup(get_welcome_message(agent_name, mode))
    
    # Main panel with consistent colors
    console.print(
        Panel(
            welcome_message,
            title="[bright_white]»»—— QUANTALOGIC QUANTUM SYSTEM ——««[/]",
            title_align="center",
            border_style=Style(color=border_color, bold=True),
            box=box.DOUBLE,
            padding=(1, 4),
            subtitle=f"[bright_cyan]QUANTUM INTELLIGENCE READY | {get_version()}[/]"
        )
    )
    
    # Print quantum equations panel at the bottom
    console.print(
        Panel(
            Text.from_markup(f"[bright_cyan]{QUANTUM_SYMBOL}[/]"),
            box=box.SIMPLE,
            style=Style(color="bright_cyan", bold=True),
            padding=(0, 2),
            title="[bright_white]QUANTUM STATE[/]",
            title_align="center"
        )
    )

# Removed banner_command as it was moved to shell.py
