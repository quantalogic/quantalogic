"""Command-line interface for running the Quantalogic Agent with event monitoring."""

import asyncio
import os
from pathlib import Path
import subprocess
import sys
from typing import Callable, List, Optional, Union

import typer
from loguru import logger
from rich.console import Console  # Optional dependency for improved output

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
from quantalogic.tools import create_tool

from .tools_manager import Tool, ToolRegistry, get_default_tools
from .utils import XMLResultHandler

app = typer.Typer(no_args_is_help=True)
console = Console()  # Rich console for enhanced output


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
        """Handle streaming token events with real-time output."""
        console.print(event.token, end="")

    async def flush_buffer(self):
        """No buffer needed with rich console."""
        pass

    async def __call__(self, event):
        """Dispatch events to their respective handlers."""
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
) -> None:
    """Run the Agent with detailed event monitoring.

    Args:
        task (str): The task to solve.
        model (str): The language model to use.
        max_iterations (int): Maximum reasoning steps.
        success_criteria (Optional[str]): Criteria to determine task completion.
        tools (Optional[List[Union[Tool, Callable]]]): Custom tools to use.
        personality (Optional[str]): Agent personality.
        backstory (Optional[str]): Agent backstory.
        sop (Optional[str]): Standard operating procedure.
        debug (bool): Enable debug logging.
        streaming (bool): Enable streaming output.
    """
    logger.remove()
    logger.add(sys.stderr, level="DEBUG" if debug else "INFO")
    logger.add(LOG_FILE, level="DEBUG" if debug else "INFO")

    tools = tools if tools is not None else get_default_tools(model)
    
    processed_tools: List[Tool] = []
    for tool in tools:
        if isinstance(tool, Tool):
            processed_tools.append(tool)
        elif callable(tool):
            processed_tools.append(create_tool(tool))
        else:
            raise ValueError(f"Invalid tool type: {type(tool)}. Expected Tool or callable.")

    config = AgentConfig(
        model=model,
        max_iterations=max_iterations,
        tools=processed_tools,
    )
    agent = Agent(
        config=config,
        personality=personality,
        backstory=backstory,
        sop=sop
    )
    
    progress_monitor = ProgressMonitor()
    solve_agent = agent
    solve_agent.add_observer(progress_monitor, [
        "TaskStarted", "ThoughtGenerated", "ActionGenerated", "ActionExecuted",
        "StepCompleted", "ErrorOccurred", "TaskCompleted", "StepStarted",
        "ToolExecutionStarted", "ToolExecutionCompleted", "ToolExecutionError",
        "StreamToken"
    ])
    
    console.print(f"[bold green]Starting task: {task}[/bold green]")
    history = await agent.solve(task, success_criteria, streaming=streaming)


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
) -> None:
    """CLI command to run the Agent with detailed event monitoring."""
    try:
        asyncio.run(run_react_agent(
            task, model, max_iterations, success_criteria,
            personality=personality, backstory=backstory, sop=sop, debug=debug,
            streaming=streaming,
        ))
    except Exception as e:
        logger.error(f"Agent failed: {e}")
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


@app.command()
def install_toolbox(
    toolbox_name: str = typer.Argument(..., help="Name of the toolbox to install (can be a PyPI package name or a path to a local wheel file)")
) -> None:
    """Install a toolbox using uv pip install. The toolbox can be specified by its PyPI package name or by a path to a local wheel file."""
    try:
        subprocess.run(["uv", "pip", "install", toolbox_name], check=True)
        console.print(f"[green]Toolbox '{toolbox_name}' installed successfully[/green]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to install toolbox: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def list_toolboxes() -> None:
    """List all loaded toolboxes from entry points."""
    logger.debug("Listing toolboxes from entry points")
    registry = ToolRegistry()
    registry.load_toolboxes()
    tools = registry.get_tools()
    if not tools:
        console.print("[yellow]No toolboxes found.[/yellow]")
    else:
        console.print("[bold cyan]Available Tools:[/bold cyan]")
        for tool in tools:
            console.print(f"- {tool.name}")


@app.command()
def create_toolbox_template(
    toolbox_name: str = typer.Argument(..., help="Name of the toolbox (e.g., math_tools)")
) -> None:
    """Create a starting point template for a new toolbox."""
    try:
        # Normalize toolbox name for directory and module names
        normalized_name = toolbox_name.lower().replace("-", "_")
        
        # Define the root directory for the new toolbox
        root_dir = Path(f"quantalogic-toolbox-{normalized_name}")
        root_dir.mkdir(exist_ok=True)
        
        # Create the package directory
        package_dir = root_dir / f"quantalogic_toolbox_{normalized_name}"
        package_dir.mkdir(exist_ok=True)
        
        # Create __init__.py
        init_file = package_dir / "__init__.py"
        init_file.touch()
        
        # Create tools.py with sample content
        tools_file = package_dir / "tools.py"
        with tools_file.open("w") as f:
            f.write(
                """
from quantalogic.tools import create_tool

# Example tool: replace or remove this in your actual toolbox
@create_tool
async def sample_tool(param: str) -> str:
    \"\"\"A sample tool that echoes the input parameter.\"\"\"
    return f"Echo: {param}"

# Add more tools here using the @create_tool decorator
"""
            )
        
        # Create pyproject.toml with configurations
        pyproject_file = root_dir / "pyproject.toml"
        with pyproject_file.open("w") as f:
            f.write(
                f"""
[tool.poetry]
name = "quantalogic-toolbox-{normalized_name}"
version = "0.1.0"
description = "A toolbox for Quantalogic providing {normalized_name} tools."
authors = ["Your Name <you@example.com>"]
dependencies = {{
    "python": ">=3.12",
    "quantalogic": ">=0.1.0",
    # Add other dependencies here
}}

[tool.poetry.plugins."quantalogic.tools"]
{normalized_name} = "quantalogic_toolbox_{normalized_name}.tools"

[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"
"""
            )
        
        console.print(f"[green]Toolbox template '{toolbox_name}' created successfully at {root_dir}[/green]")
        console.print("Next steps:")
        console.print("1. Navigate to the toolbox directory: cd", root_dir)
        console.print("2. Install dependencies: uv pip install -e .")
        console.print("3. Develop your tools in", tools_file)
        console.print("4. Test your toolbox with the Quantalogic Agent.")
    except Exception as e:
        console.print(f"[red]Failed to create toolbox template: {e}[/red]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()