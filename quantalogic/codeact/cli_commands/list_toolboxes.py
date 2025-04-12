import importlib.metadata
import typer
from pathlib import Path
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from quantalogic.codeact.cli import plugin_manager  # Import shared plugin_manager from cli.py

app = typer.Typer()
console = Console()
CONFIG_PATH = Path.home() / ".quantalogic/config.yaml"

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
        # Get entry points for quantalogic.tools
        eps = importlib.metadata.entry_points(group="quantalogic.tools")
        # Find the entry point matching the toolbox name
        ep = next((ep for ep in eps if ep.name == toolbox_name), None)
        if ep is None:
            return "Not found"
        # Load the module to get its path
        module = ep.load()
        module_file = getattr(module, "__file__", None)
        if module_file:
            return str(Path(module_file).resolve())
        return "Not found"
    except Exception:
        return "Not found"

@app.command()
def list_toolboxes(
    detail: bool = typer.Option(False, "--detail", help="Show detailed information including tools")
) -> None:
    """List installed toolboxes, optionally with detailed tool information."""
    config, status = load_config()
    
    # Display config file path and status
    console.print(f"[bold]Config file:[/bold] {CONFIG_PATH} ([italic]{status}[/italic])")
    
    installed_toolboxes = config.get("installed_toolboxes", [])
    
    if not installed_toolboxes:
        console.print("[yellow]No toolboxes installed.[/yellow]")
        return
    
    if not detail:
        # Basic output: list toolboxes with name, package, version, and module path
        console.print("[bold cyan]Installed Toolboxes:[/bold cyan]")
        for tb in installed_toolboxes:
            try:
                module_path = get_module_path(tb["name"])
                console.print(
                    f"- {tb['name']} (package: {tb['package']}, version: {tb['version']}, "
                    f"path: [italic]{module_path}[/italic])"
                )
            except Exception as e:
                console.print(f"[red]Error processing '{tb['name']}': {str(e)}[/red]")
    else:
        # Detailed output: show each toolbox with its tools in a panel
        for tb in installed_toolboxes:
            try:
                toolbox_name = tb["name"]
                package = tb["package"]
                version = tb["version"]
                # Get module path
                module_path = get_module_path(toolbox_name)
                # Filter tools by toolbox_name from the ToolRegistry
                tools = [
                    tool for (tb_name, _), tool in plugin_manager.tools.tools.items()
                    if tb_name == toolbox_name
                ]
                # Sort tools alphabetically by name
                tools.sort(key=lambda t: t.name)
                
                # Build the tool list as bullet points
                tool_list = []
                for tool in tools:
                    try:
                        tool_list.append(f"- {tool.name}: {tool.description}")
                    except Exception as e:
                        tool_list.append(f"- {tool.name}: Error retrieving description ({str(e)})")
                if not tool_list:
                    tool_list.append("- No tools found")
                
                # Create the panel content
                content = Text()
                content.append(f"Package: {package}\n")
                content.append(f"Version: {version}\n")
                content.append("Path: ")
                content.append_text(Text(module_path, style="italic"))
                content.append("\n")
                content.append("Tools:\n")
                for tool_text in tool_list:
                    content.append(tool_text + "\n")
                
                # Display the toolbox in a styled panel
                panel = Panel(
                    content,
                    title=f"[bold]{toolbox_name}[/bold]",
                    expand=False,
                    border_style="cyan"
                )
                console.print(panel)
            except Exception as e:
                console.print(f"[red]Error processing toolbox '{tb['name']}': {str(e)}[/red]")