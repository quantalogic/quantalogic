import typer
from loguru import logger
from rich.console import Console

from quantalogic.codeact.cli import plugin_manager  # Import shared plugin_manager from cli.py

app = typer.Typer()

console = Console()

@app.command()
def list_toolboxes(
    detail: bool = typer.Option(False, "--detail", "-d", help="Show detailed documentation for each tool")
) -> None:
    """List all loaded toolboxes and their associated tools from entry points.
    
    When --detail flag is used, displays the full documentation for each tool using its to_docstring() method.
    """
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
            toolbox_dict[toolbox_name].append(tool)

        for toolbox_name, tools_list in toolbox_dict.items():
            console.print(f"[bold green]Toolbox: {toolbox_name}[/bold green]")
            for tool in sorted(tools_list, key=lambda x: x.name):
                if detail:
                    # Use to_docstring() method for detailed documentation
                    docstring = tool.to_docstring()
                    console.print(f"  - [bold]{tool.name}[/bold]")
                    console.print(f"    Documentation:\n    {docstring.replace('\n', '\n    ')}")
                    console.print("")
                else:
                    console.print(f"  - {tool.name}")
            console.print("")

if __name__ == "__main__":
    app()