import typer
from pathlib import Path
import yaml
from rich.console import Console

app = typer.Typer()
console = Console()
CONFIG_PATH = Path.home() / ".quantalogic/config.yaml"

def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {"installed_toolboxes": []}
    return {"installed_toolboxes": []}

@app.command()
def list_toolboxes() -> None:
    config = load_config()
    installed_toolboxes = config.get("installed_toolboxes", [])
    
    if not installed_toolboxes:
        console.print("[yellow]No toolboxes installed.[/yellow]")
    else:
        console.print("[bold cyan]Installed Toolboxes:[/bold cyan]")
        for tb in installed_toolboxes:
            console.print(f"- {tb['name']} (package: {tb['package']}, version: {tb['version']})")