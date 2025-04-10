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
def uninstall_toolbox(
    toolbox_name: str = typer.Argument(..., help="Name of the toolbox or package to uninstall")
) -> None:
    """Uninstall a toolbox and update the config file."""
    try:
        # Load the config for updating
        config = load_config()
        eps = importlib.metadata.entry_points(group="quantalogic.tools")
        
        # Step 1: Check if input is a toolbox name (original logic)
        for ep in eps:
            if ep.name == toolbox_name:
                package_name = ep.dist.name
                subprocess.run(["uv", "pip", "uninstall", package_name], check=True)
                # Remove the specific toolbox from config
                config["installed_toolboxes"] = [tb for tb in config["installed_toolboxes"] if tb["name"] != toolbox_name]
                save_config(config)
                console.print(f"[green]Toolbox '{toolbox_name}' (package '{package_name}') uninstalled and removed from config.[/green]")
                return
        
        # Step 2: Check if input is a package name (original logic)
        package_eps = [ep for ep in eps if ep.dist.name == toolbox_name]
        if package_eps:
            subprocess.run(["uv", "pip", "uninstall", toolbox_name], check=True)
            # Remove all toolboxes provided by the package
            removed_names = [ep.name for ep in package_eps]
            config["installed_toolboxes"] = [tb for tb in config["installed_toolboxes"] if tb["name"] not in removed_names]
            save_config(config)
            toolboxes = ", ".join(removed_names)
            console.print(f"[green]Package '{toolbox_name}' providing toolbox(es) '{toolboxes}' uninstalled and removed from config.[/green]")
            return
        
        # Original case when nothing is found
        console.print(f"[yellow]No toolbox or package '{toolbox_name}' found to uninstall.[/yellow]")
    except subprocess.CalledProcessError as e:
        # Original error handling
        console.print(f"[red]Failed to uninstall: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        # Additional error handling for config updates
        console.print(f"[red]Error updating config: {e}[/red]")
        raise typer.Exit(code=1)