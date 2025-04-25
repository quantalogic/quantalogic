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
    """Print the welcome banner to the console.
    
    Args:
        agent_name: Name of the current agent
        mode: Current agent mode ('codeact' or 'chat')
        high_contrast: Whether to use high contrast colors
    """
    console = Console()
    welcome_message = Text.from_markup(get_welcome_message(agent_name, mode))
    
    border_style = Style(color="bright_blue" if high_contrast else "blue", bold=True)
    quantum_style = Style(color="bright_cyan", bold=True)
    
    # Create a smaller panel for the quantum symbol
    quantum_panel = Panel(
        Text.from_markup(f"[bright_cyan]{QUANTUM_SYMBOL}[/]"),
        box=box.SIMPLE,
        style=quantum_style,
        padding=(0, 1)
    )
    
    # Main panel with nested quantum symbol panel
    console.print(
        Panel(
            welcome_message,
            title="[bright_white]»»—— QUANTALOGIC QUANTUM SYSTEM ——««[/]",
            title_align="center",
            border_style=border_style,
            box=box.DOUBLE,
            style="dim",
            padding=(1, 4),
            subtitle=f"[bright_cyan]QUANTUM INTELLIGENCE READY | {get_version()}[/]"
        )
    )
    
    # Print quantum equations panel at the bottom
    console.print(
        Panel(
            quantum_panel,
            box=box.SIMPLE,
            style=quantum_style,
            padding=(0, 2),
            title="[bright_white]QUANTUM STATE[/]",
            title_align="center"
        )
    )
