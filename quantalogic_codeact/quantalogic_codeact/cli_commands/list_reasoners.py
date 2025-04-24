import typer
from rich.console import Console

from quantalogic_codeact.cli import plugin_manager  # Import shared plugin_manager from cli.py

app = typer.Typer()

console = Console()

@app.command()
def list_reasoners() -> None:
    """List all available reasoners."""
    console.print("[bold cyan]Available Reasoners:[/bold cyan]")
    for name in plugin_manager.reasoners.keys():
        console.print(f"- {name}")