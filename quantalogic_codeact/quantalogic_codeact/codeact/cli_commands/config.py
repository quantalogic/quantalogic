from pathlib import Path

import typer
import yaml
from rich.console import Console

console = Console()
CONFIG_PATH = Path.home() / "quantalogic-config.yaml"

app = typer.Typer()

@app.command()
def show():
    """Show the quantalogic-config.yaml file."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            config = yaml.safe_load(f) or {"installed_toolboxes": []}
        console.print("[bold cyan]Current Configuration:[/bold cyan]")
        console.print(yaml.safe_dump(config, default_flow_style=False))
    else:
        console.print("[yellow]No config file found at ~/quantalogic-config.yaml[/yellow]")

@app.command()
def reset():
    """Reset (delete) the quantalogic-config.yaml file."""
    if CONFIG_PATH.exists():
        CONFIG_PATH.unlink()
        console.print("[green]Config file reset (deleted).[/green]")
    else:
        console.print("[yellow]No config file to reset.[/yellow]")