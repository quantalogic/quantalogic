import importlib.metadata
import subprocess

import typer
from rich.console import Console

app = typer.Typer()

console = Console()

@app.command()
def uninstall_toolbox(
    toolbox_name: str = typer.Argument(..., help="Name of the toolbox or package to uninstall")
) -> None:
    """Uninstall a toolbox by its name or the package name that provides it."""
    try:
        # Get all entry points in the "quantalogic.tools" group
        eps = importlib.metadata.entry_points(group="quantalogic.tools")
        
        # Step 1: Check if the input is a toolbox name (entry point name)
        for ep in eps:
            if ep.name == toolbox_name:
                package_name = ep.dist.name
                subprocess.run(["uv", "pip", "uninstall", package_name], check=True)
                console.print(f"[green]Toolbox '{toolbox_name}' (package '{package_name}') uninstalled successfully[/green]")
                return
        
        # Step 2: Check if the input is a package name providing any toolbox
        package_eps = [ep for ep in eps if ep.dist.name == toolbox_name]
        if package_eps:
            subprocess.run(["uv", "pip", "uninstall", toolbox_name], check=True)
            toolboxes = ", ".join(ep.name for ep in package_eps)
            console.print(f"[green]Package '{toolbox_name}' providing toolbox(es) '{toolboxes}' uninstalled successfully[/green]")
            return
        
        # If neither a toolbox nor a package is found
        console.print(f"[yellow]No toolbox or package '{toolbox_name}' found to uninstall[/yellow]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to uninstall: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]An error occurred: {e}[/red]")
        raise typer.Exit(code=1)