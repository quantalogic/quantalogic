import importlib.metadata
import re
import subprocess
from pathlib import Path

import typer
import yaml
from rich.console import Console

app = typer.Typer()
console = Console()
GLOBAL_CONFIG_PATH = Path.home() / ".quantalogic/config.yaml"
PROJECT_CONFIG_PATH = Path(".quantalogic/config.yaml").resolve()

def load_config(path: Path):
    """Load or initialize the config file."""
    if path.exists():
        with open(path) as f:
            return yaml.safe_load(f) or {"installed_toolboxes": []}
    return {"installed_toolboxes": []}

def save_config(config, path: Path):
    """Save the config to file."""
    path.parent.mkdir(exist_ok=True)
    with open(path, "w") as f:
        yaml.safe_dump(config, f, default_flow_style=False)

def parse_package_info_from_filename(filename):
    """Parse package name and version from filename like 'package_name-1.0.0.tar.gz'"""
    match = re.match(r"(.+)-(\d+\.\d+\.\d+)", Path(filename).stem)
    if match:
        return match.group(1), match.group(2)
    return None, None

@app.command()
def install_toolbox(
    toolbox_name: str = typer.Argument(..., help="Name of the toolbox to install (PyPI package or local wheel file)"),
    enable: bool = typer.Option(False, "--enable", help="Automatically enable the toolbox in the project's configuration")
) -> None:
    """Install a toolbox, update the global config, and optionally enable it in the project config."""
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
        global_config = load_config(GLOBAL_CONFIG_PATH)
        
        # Remove existing entries for this package
        global_config["installed_toolboxes"] = [tb for tb in global_config["installed_toolboxes"] if tb["package"] != package_name]
        
        # Get entry points for this package
        eps = importlib.metadata.entry_points(group="quantalogic.tools")
        installed_eps = [ep for ep in eps if ep.dist.name == package_name]
        
        if not installed_eps:
            console.print(f"[yellow]Installed '{package_name}' but no quantalogic.tools entry points found.[/yellow]")
            global_config["installed_toolboxes"].append({
                "name": package_name,
                "package": package_name,
                "version": version
            })
        else:
            from quantalogic_codeact.codeact.cli import plugin_manager
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
        
        save_config(global_config, GLOBAL_CONFIG_PATH)
        console.print(f"[green]Toolbox '{package_name}' installed and added to global config.[/green]")
        
        if enable:
            # Load project config
            project_config = load_config(PROJECT_CONFIG_PATH)
            enabled_toolboxes = project_config.get("enabled_toolboxes", [])
            for ep in installed_eps:
                if ep.name not in enabled_toolboxes:
                    enabled_toolboxes.append(ep.name)
            project_config["enabled_toolboxes"] = enabled_toolboxes
            save_config(project_config, PROJECT_CONFIG_PATH)
            console.print(f"[green]Toolbox '{package_name}' enabled in project config.[/green]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to install toolbox: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)