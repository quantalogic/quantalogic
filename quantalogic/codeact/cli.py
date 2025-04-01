"""Command-line interface for running the Quantalogic Agent with event monitoring."""

import asyncio
import importlib.metadata
import subprocess
import sys
from typing import Callable, List, Optional, Union

import typer
from loguru import logger
from rich.console import Console

from quantalogic.codeact.agent import Agent, AgentConfig
from quantalogic.codeact.constants import DEFAULT_MODEL, LOG_FILE
from quantalogic.codeact.events import (
    ActionExecutedEvent,
    ActionGeneratedEvent,
    ErrorOccurredEvent,
    StepCompletedEvent,
    StepStartedEvent,
    StreamTokenEvent,
    TaskCompletedEvent,
    TaskStartedEvent,
    ThoughtGeneratedEvent,
    ToolExecutionCompletedEvent,
    ToolExecutionErrorEvent,
    ToolExecutionStartedEvent,
)
from quantalogic.codeact.plugin_manager import PluginManager

from .tools_manager import Tool, get_default_tools
from .utils import process_tools
from .xml_utils import XMLResultHandler

# Initialize PluginManager at module level to avoid duplicate loading
plugin_manager = PluginManager()
plugin_manager.load_plugins()

app = typer.Typer(no_args_is_help=True)
console = Console()


class ProgressMonitor:
    """Handles progress monitoring for agent events."""
    def __init__(self):
        self._token_buffer = ""

    async def on_task_started(self, event: TaskStartedEvent):
        console.print(f"[bold green]Task Started: {event.task_description}[/bold green]")
        console.print(f"Timestamp: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        console.print("-" * 50)

    async def on_thought_generated(self, event: ThoughtGeneratedEvent):
        console.print(f"[bold cyan]Step {event.step_number} - Thought Generated:[/bold cyan]")
        console.print(f"Thought: {event.thought}")
        console.print(f"Generation Time: {event.generation_time:.2f} seconds")
        console.print("-" * 50)

    async def on_action_generated(self, event: ActionGeneratedEvent):
        console.print(f"[bold blue]Step {event.step_number} - Action Generated:[/bold blue]")
        console.print(f"Action Code:\n{event.action_code}")
        console.print(f"Generation Time: {event.generation_time:.2f} seconds")
        console.print("-" * 50)

    async def on_action_executed(self, event: ActionExecutedEvent):
        summary = XMLResultHandler.format_result_summary(event.result_xml)
        console.print(f"[bold magenta]Step {event.step_number} - Action Executed:[/bold magenta]")
        console.print(f"Result Summary:\n{summary}")
        console.print(f"Execution Time: {event.execution_time:.2f} seconds")
        console.print("-" * 50)

    async def on_step_completed(self, event: StepCompletedEvent):
        console.print(f"[bold yellow]Step {event.step_number} - Completed[/bold yellow]")
        console.print("-" * 50)

    async def on_error_occurred(self, event: ErrorOccurredEvent):
        console.print(f"[bold red]Error Occurred{' at Step ' + str(event.step_number) if event.step_number else ''}:[/bold red]")
        console.print(f"Message: {event.error_message}")
        console.print(f"Timestamp: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        console.print("-" * 50)

    async def on_task_completed(self, event: TaskCompletedEvent):
        if event.final_answer:
            console.print("[bold green]Task Completed Successfully:[/bold green]")
            console.print(f"Final Answer:\n{event.final_answer}")
        else:
            console.print("[bold red]Task Did Not Complete Successfully:[/bold red]")
            console.print(f"Reason: {event.reason}")
        console.print(f"Timestamp: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        console.print("-" * 50)

    async def on_step_started(self, event: StepStartedEvent):
        console.print(f"[bold yellow]Starting Step {event.step_number}[/bold yellow]")
        console.print("-" * 50)

    async def on_tool_execution_started(self, event: ToolExecutionStartedEvent):
        console.print(f"[cyan]Tool {event.tool_name} started execution at step {event.step_number}[/cyan]")
        console.print(f"Parameters: {event.parameters_summary}")

    async def on_tool_execution_completed(self, event: ToolExecutionCompletedEvent):
        console.print(f"[green]Tool {event.tool_name} completed execution at step {event.step_number}[/green]")
        console.print(f"Result: {event.result_summary}")

    async def on_tool_execution_error(self, event: ToolExecutionErrorEvent):
        console.print(f"[red]Tool {event.tool_name} encountered an error at step {event.step_number}[/red]")
        console.print(f"Error: {event.error}")

    async def on_stream_token(self, event: StreamTokenEvent):
        console.print(event.token, end="")

    async def flush_buffer(self):
        pass

    async def __call__(self, event):
        if isinstance(event, TaskStartedEvent):
            await self.on_task_started(event)
        elif isinstance(event, ThoughtGeneratedEvent):
            await self.on_thought_generated(event)
        elif isinstance(event, ActionGeneratedEvent):
            await self.on_action_generated(event)
            await self.flush_buffer()
        elif isinstance(event, ActionExecutedEvent):
            await self.on_action_executed(event)
        elif isinstance(event, StepCompletedEvent):
            await self.on_step_completed(event)
        elif isinstance(event, ErrorOccurredEvent):
            await self.on_error_occurred(event)
        elif isinstance(event, TaskCompletedEvent):
            await self.on_task_completed(event)
            await self.flush_buffer()
        elif isinstance(event, StepStartedEvent):
            await self.on_step_started(event)
        elif isinstance(event, ToolExecutionStartedEvent):
            await self.on_tool_execution_started(event)
        elif isinstance(event, ToolExecutionCompletedEvent):
            await self.on_tool_execution_completed(event)
        elif isinstance(event, ToolExecutionErrorEvent):
            await self.on_tool_execution_error(event)
        elif isinstance(event, StreamTokenEvent):
            await self.on_stream_token(event)


async def run_react_agent(
    task: str,
    model: str,
    max_iterations: int,
    success_criteria: Optional[str] = None,
    tools: Optional[List[Union[Tool, Callable]]] = None,
    personality: Optional[str] = None,
    backstory: Optional[str] = None,
    sop: Optional[str] = None,
    debug: bool = False,
    streaming: bool = False,
    reasoner_name: Optional[str] = None,
    executor_name: Optional[str] = None,
) -> None:
    """Run the Agent with detailed event monitoring."""
    logger.remove()
    logger.add(sys.stderr, level="DEBUG" if debug else "INFO")
    logger.add(LOG_FILE, level="DEBUG" if debug else "INFO")

    tools = tools if tools is not None else get_default_tools(model)
    processed_tools = process_tools(tools)

    # Create AgentConfig with all parameters
    config = AgentConfig(
        model=model,
        max_iterations=max_iterations,
        tools=processed_tools,
        personality=personality,
        backstory=backstory,
        sop=sop,
        reasoner_name=reasoner_name if reasoner_name else "default",
        executor_name=executor_name if executor_name else "default",
    )
    
    agent = Agent(config=config)
    
    progress_monitor = ProgressMonitor()
    solve_agent = agent
    solve_agent.add_observer(progress_monitor, [
        "TaskStarted", "ThoughtGenerated", "ActionGenerated", "ActionExecuted",
        "StepCompleted", "ErrorOccurred", "TaskCompleted", "StepStarted",
        "ToolExecutionStarted", "ToolExecutionCompleted", "ToolExecutionError",
        "StreamToken"
    ])
    
    console.print(f"[bold green]Starting task: {task}[/bold green]")
    _history = await agent.solve(task, success_criteria, streaming=streaming,
                                reasoner_name=reasoner_name, executor_name=executor_name)


@app.command()
def task(
    task: str = typer.Argument(..., help="The task to solve"),
    model: str = typer.Option(DEFAULT_MODEL, help="The litellm model to use"),
    max_iterations: int = typer.Option(5, help="Maximum reasoning steps"),
    success_criteria: Optional[str] = typer.Option(None, help="Optional criteria to determine task completion"),
    personality: Optional[str] = typer.Option(None, help="Agent personality (e.g., 'witty')"),
    backstory: Optional[str] = typer.Option(None, help="Agent backstory"),
    sop: Optional[str] = typer.Option(None, help="Standard operating procedure"),
    debug: bool = typer.Option(False, help="Enable debug logging to stderr"),
    streaming: bool = typer.Option(False, help="Enable streaming output for real-time token generation"),
    reasoner: Optional[str] = typer.Option(None, help="Name of the reasoner to use"),
    executor: Optional[str] = typer.Option(None, help="Name of the executor to use"),
) -> None:
    """CLI command to run the Agent with detailed event monitoring."""
    try:
        asyncio.run(run_react_agent(
            task, model, max_iterations, success_criteria,
            personality=personality, backstory=backstory, sop=sop, debug=debug,
            streaming=streaming, reasoner_name=reasoner, executor_name=executor
        ))
    except Exception as e:
        logger.error(f"Agent failed: {e}")
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


@app.command()
def install_toolbox(
    toolbox_name: str = typer.Argument(..., help="Name of the toolbox to install (PyPI package or local wheel file)")
) -> None:
    """Install a toolbox using uv pip install."""
    try:
        subprocess.run(["uv", "pip", "install", toolbox_name], check=True)
        console.print(f"[green]Toolbox '{toolbox_name}' installed successfully[/green]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to install toolbox: {e}[/red]")
        raise typer.Exit(code=1)


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


@app.command()
def list_reasoners() -> None:
    """List all available reasoners."""
    console.print("[bold cyan]Available Reasoners:[/bold cyan]")
    for name in plugin_manager.reasoners.keys():
        console.print(f"- {name}")


@app.command()
def list_executors() -> None:
    """List all available executors."""
    console.print("[bold cyan]Available Executors:[/bold cyan]")
    for name in plugin_manager.executors.keys():
        console.print(f"- {name}")


@app.command()
def tool_info(tool_name: str = typer.Argument(..., help="Name of the tool")) -> None:
    """Display information about a specific tool."""
    tools = plugin_manager.tools.get_tools()
    tool = next((t for t in tools if t.name == tool_name), None)
    if tool:
        console.print(f"[bold green]Tool: {tool.name}[/bold green]")
        console.print(f"Description: {tool.description}")
        console.print(f"Toolbox: {tool.toolbox_name or 'N/A'}")
        console.print("Arguments:")
        for arg in tool.arguments:
            console.print(f"  - {arg.name} ({arg.arg_type}): {arg.description} {'(required)' if arg.required else ''}")
        console.print(f"Return Type: {tool.return_type}")
    else:
        console.print(f"[red]Tool '{tool_name}' not found[/red]")


# Load plugin CLI commands dynamically using the module-level plugin_manager
for cmd_name, cmd_func in plugin_manager.cli_commands.items():
    app.command(name=cmd_name)(cmd_func)


if __name__ == "__main__":
    app()