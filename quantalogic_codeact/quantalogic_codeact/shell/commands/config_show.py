from typing import List

from jinja2 import Environment
from rich.console import Console
from rich.table import Table
import quantalogic_codeact.codeact.cli_commands.config_manager as config_manager

console = Console()

async def config_show(shell, args: List[str]) -> str:
    """Display the current configuration with sanitized values."""
    config_path = config_manager.GLOBAL_CONFIG_PATH.expanduser().resolve()
    console.print(f"[bold]Config file path:[/bold] {config_path}")
    config = shell.current_agent.config
    # Collect raw attributes (exclude private)
    raw = {k: v for k, v in vars(config).items() if not k.startswith('_')}
    # Recursively sanitize values to serializable primitives or repr
    def sanitize(val):
        # Primitive types
        if isinstance(val, (str, int, float, bool, type(None))):
            return val
        # Special-case Jinja2 Environment
        if isinstance(val, Environment):
            return "<jinja2.Environment>"
        # Nested structures
        if isinstance(val, dict):
            return {sanitize(k): sanitize(v) for k, v in val.items()}
        if isinstance(val, (list, tuple)):
            return [sanitize(v) for v in val]
        # Fallback for other non-serializable objects
        return repr(val)
    sanitized = {k: sanitize(v) for k, v in raw.items()}
    # Render configuration as a styled table
    table = Table(title="Current Configuration", show_header=True, header_style="bold magenta")
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")
    for key, value in sanitized.items():
        table.add_row(str(key), str(value))
    console.print(table)
    return ""