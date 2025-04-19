import importlib.metadata
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from quantalogic_codeact.codeact.cli import plugin_manager  # Import shared plugin_manager from cli.py

app = typer.Typer()
console = Console()
CONFIG_PATH = Path.home() / ".quantalogic/config.yaml"
PROJECT_CONFIG_PATH = Path(".quantalogic/config.yaml").resolve()

def load_config():
    """Load the configuration file and return the config along with a status message."""
    if not CONFIG_PATH.exists():
        return {"installed_toolboxes": []}, "not found"
    try:
        with open(CONFIG_PATH) as f:
            config = yaml.safe_load(f)
            if config is None:
                return {"installed_toolboxes": []}, "empty"
            return config, "loaded"
    except yaml.YAMLError:
        return {"installed_toolboxes": []}, "invalid YAML"
    except Exception as e:
        return {"installed_toolboxes": []}, f"error: {str(e)}"

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
    config, status = load_config()
    # Load project config to determine enabled toolboxes
    enabled_toolboxes = []
    if PROJECT_CONFIG_PATH.exists():
        try:
            with open(PROJECT_CONFIG_PATH) as f:
                proj_cfg = yaml.safe_load(f) or {}
                enabled_toolboxes = proj_cfg.get("enabled_toolboxes", [])
        except Exception:
            pass
    
    console.print(f"[bold]Config file:[/bold] {CONFIG_PATH} ([italic]{status}[/italic])")
    
    installed_toolboxes = config.get("installed_toolboxes", [])
    
    if not installed_toolboxes:
        console.print("[yellow]No toolboxes installed.[/yellow]")
        return
    
    if not detail:
        console.print("[bold cyan]Installed Toolboxes:[/bold cyan]")
        for tb in installed_toolboxes:
            try:
                module_path = get_module_path(tb["name"])
                status_mark = "[green]enabled[/green]" if tb["name"] in enabled_toolboxes else "[dim]disabled[/dim]"
                console.print(
                    f"- {tb['name']} {status_mark} (package: {tb['package']}, version: {tb['version']}, "
                    f"path: [italic]{module_path}[/italic])"
                )
            except Exception as e:
                console.print(f"[red]Error processing '{tb['name']}': {str(e)}[/red]")
    else:
        plugin_manager.load_plugins(force=True)  # Force reload to ensure latest tools
        for tb in installed_toolboxes:
            try:
                toolbox_name = tb["name"]
                package = tb["package"]
                version = tb["version"]
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
                console.print(f"[red]Error processing toolbox '{tb['name']}': {str(e)}[/red]")