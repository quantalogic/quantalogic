import typer
from rich.console import Console

from quantalogic_codeact.cli import plugin_manager  # Import shared plugin_manager from cli.py

app = typer.Typer()

console = Console()

@app.command()
def tool_info(tool_name: str = typer.Argument(..., help="Name of the tool")) -> None:
    """Display information about a specific tool."""
    tools = plugin_manager.tools.get_tools()
    tool = next((t for t in tools if t.name == tool_name), None)
    if tool:
        try:
            console.print(f"[bold green]Tool: {tool.name}[/bold green]")
            console.print(f"Description: {tool.description}")
            console.print(f"Toolbox: {tool.toolbox_name or 'N/A'}")
            console.print("Arguments:")
            for arg in tool.arguments:
                console.print(f"  - {arg.name} ({arg.arg_type}): {arg.description} {'(required)' if arg.required else ''}")
            console.print(f"Return Type: {tool.return_type}")
        except Exception as e:
            console.print(f"[red]Error retrieving information for tool '{tool_name}': {str(e)}[/red]")
    else:
        console.print(f"[red]Tool '{tool_name}' not found[/red]")