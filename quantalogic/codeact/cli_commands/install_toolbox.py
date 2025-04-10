import importlib.metadata
import subprocess
from pathlib import Path

import typer
import yaml
from rich.console import Console

app = typer.Typer()
console = Console()
CONFIG_PATH = Path.home() / "quantalogic-config.yaml"

def load_config():
    """Load or initialize the config file."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {"installed_toolboxes": []}
    return {"installed_toolboxes": []}

def save_config(config):
    """Save the config to file."""
    with open(CONFIG_PATH, "w") as f:
        yaml.safe_dump(config, f, default_flow_style=False)

@app.command()
def install_toolbox(
    toolbox_name: str = typer.Argument(..., help="Name of the toolbox to install (PyPI package or local wheel file)")
) -> None:
    """Install a toolbox and update the config file."""
    try:
        # Install the toolbox using uv pip install (original feature)
        subprocess.run(["uv", "pip", "install", toolbox_name], check=True)
        
        # Load existing config
        config = load_config()
        
        # Check if the package is already installed to avoid duplicates
        if any(tb["package"] == toolbox_name for tb in config["installed_toolboxes"]):
            console.print(f"[yellow]Toolbox package '{toolbox_name}' is already installed.[/yellow]")
            return
        
        # Retrieve toolbox details from entry points
        eps = importlib.metadata.entry_points(group="quantalogic.tools")
        installed_eps = [ep for ep in eps if ep.dist.name == toolbox_name]
        if not installed_eps:
            console.print(f"[yellow]Installed '{toolbox_name}' but no quantalogic.tools entry points found.[/yellow]")
            entry_name = toolbox_name  # Fallback to package name if no entry points
        else:
            entry_name = installed_eps[0].name  # Use the first entry point name
        
        # Get the package version, with fallback for robustness
        try:
            version = importlib.metadata.version(toolbox_name)
        except importlib.metadata.PackageNotFoundError:
            version = "unknown"
        
        # Update the config with the new toolbox details
        config["installed_toolboxes"].append({
            "name": entry_name,
            "package": toolbox_name,
            "version": version
        })
        save_config(config)
        
        # Success message styled with rich.console (preserving original style)
        console.print(f"[green]Toolbox '{entry_name}' (package '{toolbox_name}') installed and added to config.[/green]")
    except subprocess.CalledProcessError as e:
        # Original error handling preserved
        console.print(f"[red]Failed to install toolbox: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        # Additional error handling for config operations
        console.print(f"[red]Error updating config: {e}[/red]")
        raise typer.Exit(code=1)