import typer
import yaml
from rich.console import Console

import quantalogic_codeact.cli_commands.config_manager as config_manager

console = Console()

app = typer.Typer()

@app.command()
def show():
    """Show the quantalogic-config.yaml file."""
    path = config_manager.GLOBAL_CONFIG_PATH.expanduser().resolve()
    console.print(f"[bold]Config file path:[/bold] {path}")
    if path.exists():
        with open(path) as f:
            config = yaml.safe_load(f) or {"installed_toolboxes": []}
        console.print("[bold cyan]Current Configuration:[/bold cyan]")
        console.print(yaml.safe_dump(config, default_flow_style=False))
    else:
        console.print(f"[yellow]No config file found at {path}[/yellow]")

@app.command()
def reset():
    """Reset (delete) the quantalogic-config.yaml file."""
    path = config_manager.GLOBAL_CONFIG_PATH.expanduser().resolve()
    if path.exists():
        path.unlink()
        console.print("[green]Config file reset (deleted).[/green]")
    else:
        console.print("[yellow]No config file to reset.[/yellow]")