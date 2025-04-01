import typer
from loguru import logger
from rich.console import Console

from quantalogic.codeact.cli import plugin_manager  # Import shared plugin_manager from cli.py

app = typer.Typer()

console = Console()

@app.command()
def list_toolboxes() -> None:
    """List all loaded toolboxes and their associated tools from entry points."""
    logger.debug("Listing toolboxes from entry points")
    tools = plugin_manager.tools.get_tools()

    if not tools:
        console.print("[yellow]No toolboxes found.[/yellow]")
    else:
        console.print("[bold cyan]Available Toolboxes and Tools:[/bold cyan]")
        toolbox_dict = {}
        for tool in tools:
            toolbox_name = tool.toolbox_name if tool.toolbox_name else 'Unknown Toolbox'
            if toolbox_name not in toolbox_dict:
                toolbox_dict[toolbox_name] = []
            toolbox_dict[toolbox_name].append(tool.name)

        for toolbox_name, tool_names in toolbox_dict.items():
            console.print(f"[bold green]Toolbox: {toolbox_name}[/bold green]")
            for tool_name in sorted(tool_names):
                console.print(f"  - {tool_name}")
            console.print("")