import importlib.metadata
import subprocess
from pathlib import Path

import typer
import yaml
from rich.console import Console

app = typer.Typer()
console = Console()
CONFIG_PATH = Path.home() / ".quantalogic/config.yaml"

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
def uninstall_toolbox(
    toolbox_name: str = typer.Argument(..., help="Name of the toolbox or package to uninstall")
) -> None:
    """Uninstall a toolbox and update the config file."""
    try:
        # Load current configuration
        config = load_config()
        
        # Step 1: Check if input is a toolbox name
        toolbox_entry = next((tb for tb in config["installed_toolboxes"] if tb["name"] == toolbox_name), None)
        if toolbox_entry:
            package_name = toolbox_entry["package"]
            subprocess.run(["uv", "pip", "uninstall", package_name], check=True)
            config["installed_toolboxes"] = [tb for tb in config["installed_toolboxes"] if tb["name"] != toolbox_name]
            save_config(config)
            console.print(f"[green]Toolbox '{toolbox_name}' (package '{package_name}') uninstalled and removed from config.[/green]")
            return
        
        # Step 2: Check if input is a package name
        package_entries = [tb for tb in config["installed_toolboxes"] if tb["package"] == toolbox_name]
        if package_entries:
            subprocess.run(["uv", "pip", "uninstall", toolbox_name], check=True)
            config["installed_toolboxes"] = [tb for tb in config["installed_toolboxes"] if tb["package"] != toolbox_name]
            save_config(config)
            toolbox_names = ", ".join(tb["name"] for tb in package_entries)
            console.print(f"[green]Package '{toolbox_name}' providing toolbox(es) '{toolbox_names}' uninstalled and removed from config.[/green]")
            return
        
        # If neither toolbox nor package is found
        console.print(f"[yellow]No toolbox or package '{toolbox_name}' found to uninstall.[/yellow]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to uninstall: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error updating config: {e}[/red]")
        raise typer.Exit(code=1)