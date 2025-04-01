import subprocess

import typer
from rich.console import Console

app = typer.Typer()

console = Console()

@app.command()
def install_toolbox(
    toolbox_name: str = typer.Argument(..., help="Name of the toolbox to install (PyPI package or local wheel file)")
) -> None:
    """Install a toolbox using uv pip install."""
    try:
        subprocess.run(["uv", "pip", "install", toolbox_name], check=True)
        console.print(f"[green]Toolbox '{toolbox_name}' installed successfully[/green]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to install toolbox: {e}[/red]")
        raise typer.Exit(code=1)