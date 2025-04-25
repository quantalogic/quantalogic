import typer
from rich.console import Console

from quantalogic_codeact.cli import plugin_manager  # Import shared plugin_manager from cli.py

app = typer.Typer()

console = Console()

@app.command()
def list_executors() -> None:
    """List all available executors."""
    console.print("[bold cyan]Available Executors:[/bold cyan]")
    for name in plugin_manager.executors.keys():
        console.print(f"- {name}")