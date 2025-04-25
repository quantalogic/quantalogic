import importlib.metadata
import re
import subprocess
from pathlib import Path

import typer
from rich.console import Console

from quantalogic_codeact.cli_commands.config_functions import load_global_config, save_global_config

app = typer.Typer()
console = Console()

def parse_package_info_from_filename(filename):
    """Parse package name and version from filename like 'package_name-1.0.0.tar.gz'"""
    match = re.match(r"(.+)-(\d+\.\d+\.\d+)", Path(filename).stem)
    if match:
        return match.group(1), match.group(2)
    return None, None

@app.command()
def install_toolbox(
    toolbox_name: str = typer.Argument(..., help="Name of the toolbox to install (PyPI package or local wheel file)")
) -> None:
    """Install a toolbox, update the global config, and enable it in the global config."""
    try:
        # Determine package name and version based on input
        if Path(toolbox_name).exists():
            parsed_package_name, parsed_version = parse_package_info_from_filename(toolbox_name)
            if not parsed_package_name:
                raise ValueError("Cannot parse package name from filename")
            package_name = parsed_package_name
            version = parsed_version or "unknown"
        else:
            package_name = toolbox_name
            version = "unknown"
        
        # Install the toolbox
        subprocess.run(["uv", "pip", "install", toolbox_name], check=True)
        
        # Try to get the actual version after installation
        try:
            version = importlib.metadata.version(package_name)
        except importlib.metadata.PackageNotFoundError:
            pass
        
        # Load existing global config
        global_config = load_global_config()
        
        # Remove existing entries for this package
        global_config["installed_toolboxes"] = [tb for tb in global_config["installed_toolboxes"] if tb["package"] != package_name]
        
        # Get entry points for this package
        eps = importlib.metadata.entry_points(group="quantalogic.tools")
        # Match distribution name with underscores or dashes
        dist_names = {package_name, package_name.replace("_", "-")}
        installed_eps = [ep for ep in eps if ep.dist.name in dist_names]
        
        if not installed_eps:
            console.print(f"[yellow]Installed '{package_name}' but no quantalogic.tools entry points found.[/yellow]")
            global_config["installed_toolboxes"].append({
                "name": package_name,
                "package": package_name,
                "version": version
            })
        else:
            from quantalogic_codeact.cli import plugin_manager
            for ep in installed_eps:
                # Load the module and register tools
                try:
                    module = ep.load()
                    if hasattr(module, 'get_tools'):
                        plugin_manager.tools.register_tools_from_module(module, toolbox_name=ep.name)
                        console.print(f"[green]Tools registered for toolbox '{ep.name}'[/green]")
                    global_config["installed_toolboxes"].append({
                        "name": ep.name,
                        "package": package_name,
                        "version": version
                    })
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not register tools for '{ep.name}': {e}[/yellow]")
        
        # Persist installation
        save_global_config(global_config)
        console.print(f"[green]Toolbox '{package_name}' installed and added to global config.[/green]")
        
        # Enable toolboxes
        to_enable = [ep.name for ep in installed_eps] or [package_name]
        for name in to_enable:
            if name not in global_config.setdefault("enabled_toolboxes", []):
                global_config["enabled_toolboxes"].append(name)
        save_global_config(global_config)
        console.print(f"[green]Toolbox '{', '.join(to_enable)}' enabled in global config.[/green]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to install toolbox: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)