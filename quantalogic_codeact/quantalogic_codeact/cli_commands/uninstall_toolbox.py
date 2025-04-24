import typer
from rich.console import Console

from quantalogic_codeact.cli_commands.config_functions import load_project_config, save_project_config
from quantalogic_codeact.commands.toolbox.uninstall_toolbox_core import uninstall_toolbox_core

app = typer.Typer()
console = Console()

@app.command()
def uninstall_toolbox(
    toolbox_name: str = typer.Argument(..., help="Name of the toolbox or package to uninstall")
) -> None:
    """Uninstall a toolbox and update both global and project configs."""
    # Core global uninstall (pip uninstall + global config save)
    messages = uninstall_toolbox_core(toolbox_name)
    for msg in messages:
        console.print(msg)
    # Disable in project config
    project_cfg = load_project_config()
    enabled = project_cfg.get("enabled_toolboxes", [])
    if toolbox_name in enabled:
        enabled.remove(toolbox_name)
        project_cfg["enabled_toolboxes"] = enabled
        save_project_config(project_cfg)
        console.print(f"[green]Toolbox '{toolbox_name}' disabled in project config.[/green]")