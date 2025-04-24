import importlib.metadata
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from quantalogic_codeact.cli import plugin_manager
from quantalogic_codeact.cli_commands.config_constants import GLOBAL_CONFIG_PATH
from quantalogic_codeact.cli_commands.config_functions import load_global_config

app = typer.Typer()
console = Console()

def get_module_path(toolbox_name: str) -> str:
    """Retrieve the filesystem path of the module for a given toolbox."""
    try:
        eps = importlib.metadata.entry_points(group="quantalogic.tools")
        ep = next((ep for ep in eps if ep.name == toolbox_name), None)
        if ep is None:
            return "Not found"
        module = ep.load()
        module_file = getattr(module, "__file__", None)
        if module_file:
            return str(Path(module_file).resolve())
        return "Not found"
    except Exception:
        return "Not found"

@app.command()
def list_toolboxes(
    detail: bool = typer.Option(False, "--detail", help="Show detailed information including tools and their documentation")
) -> None:
    """List installed toolboxes, optionally with detailed tool information and documentation."""
    # Load config
    config = load_global_config()
    
    console.print(f"[bold]Config file:[/bold] {GLOBAL_CONFIG_PATH}")
    
    installed_toolboxes = config.installed_toolboxes or []
    
    if not installed_toolboxes:
        console.print("[yellow]No toolboxes installed.[/yellow]")
        return
    
    if not detail:
        console.print("[bold cyan]Installed Toolboxes:[/bold cyan]")
        for tb in installed_toolboxes:
            try:
                module_path = get_module_path(tb.name)
                status_mark = "[green]enabled[/green]" if tb.enabled else "[dim]disabled[/dim]"
                console.print(
                    f"- {tb.name} {status_mark} (package: {tb.package}, version: {tb.version}, "
                    f"path: [italic]{module_path}[/italic])"
                )
            except Exception as e:
                console.print(f"[red]Error processing '{tb.name}': {str(e)}[/red]")
    else:
        plugin_manager.load_plugins(force=True)  # Force reload to ensure latest tools
        for tb in installed_toolboxes:
            try:
                toolbox_name = tb.name
                package = tb.package
                version = tb.version
                module_path = get_module_path(toolbox_name)
                tools = [
                    tool for (tb_name, _), tool in plugin_manager.tools.tools.items()
                    if tb_name == toolbox_name
                ]
                tools.sort(key=lambda t: t.name)
                
                tool_list = []
                for tool in tools:
                    try:
                        docstring = tool.to_docstring().strip() if hasattr(tool, 'to_docstring') else "No documentation available"
                        tool_list.append(f"- {tool.name}:\n  {docstring}")
                    except Exception as e:
                        tool_list.append(f"- {tool.name}: Error retrieving documentation ({str(e)})")
                if not tool_list:
                    tool_list.append("- No tools found")
                
                content = Text()
                content.append(f"Package: {package}\n")
                content.append(f"Version: {version}\n")
                content.append("Path: ")
                content.append_text(Text(module_path, style="italic"))
                content.append("\n")
                content.append("Tools:\n")
                for tool_text in tool_list:
                    content.append(tool_text + "\n")
                
                panel = Panel(
                    content,
                    title=f"[bold]{toolbox_name}[/bold]",
                    expand=False,
                    border_style="cyan"
                )
                console.print(panel)
            except Exception as e:
                console.print(f"[red]Error processing toolbox '{tb.name}': {str(e)}[/red]")