import asyncio

import typer
from rich.console import Console

from quantalogic_codeact.codeact.plugin_manager import PluginManager
from quantalogic_codeact.commands.toolbox import (
    get_tool_doc,
    install_toolbox,
    list_toolbox_tools,
    uninstall_toolbox,
)

app = typer.Typer()
console = Console()

class DummyShell:
    """A minimal shell-like object to pass to toolbox commands for CLI compatibility."""
    def __init__(self):
        self.debug = False
        self.current_agent = DummyAgent()

class DummyAgent:
    """A minimal agent-like object providing plugin_manager for CLI commands."""
    def __init__(self):
        self.plugin_manager = PluginManager()
        self.plugin_manager.load_plugins()

@app.command()
def install(toolbox_name: str = typer.Argument(..., help="Name of the toolbox to install")):
    """Install a toolbox."""
    shell = DummyShell()
    result = asyncio.run(install_toolbox(shell, [toolbox_name]))
    console.print(result)

@app.command()
def uninstall(toolbox_name: str = typer.Argument(..., help="Name of the toolbox to uninstall")):
    """Uninstall a toolbox."""
    shell = DummyShell()
    result = asyncio.run(uninstall_toolbox(shell, [toolbox_name]))
    console.print(result)

@app.command()
def tools(toolbox_name: str = typer.Argument(..., help="Name of the toolbox")):
    """List tools in a toolbox."""
    shell = DummyShell()
    result = list_toolbox_tools(shell, [toolbox_name])
    console.print(result)

@app.command()
def doc(toolbox_name: str = typer.Argument(..., help="Name of the toolbox"),
       tool_name: str = typer.Argument(..., help="Name of the tool")):
    """Show documentation for a tool in a toolbox."""
    shell = DummyShell()
    result = get_tool_doc(shell, [toolbox_name, tool_name])
    console.print(result)