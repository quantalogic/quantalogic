import asyncio
import json
import sys

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
from quantalogic.codeact.tools_manager import get_default_tools
from quantalogic.codeact.utils import process_tools
from quantalogic.codeact.xml_utils import XMLResultHandler

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
    success_criteria: str = None,
    tools=None,
    personality=None,
    backstory=None,
    sop=None,
    debug: bool = False,
    streaming: bool = False,
    reasoner_name=None,
    executor_name=None,
    tools_config=None,
    profile=None,
    customizations=None
) -> None:
    """Run the Agent with detailed event monitoring."""
    logger.remove()
    logger.add(sys.stderr, level="DEBUG" if debug else "INFO")
    logger.add(LOG_FILE, level="DEBUG" if debug else "INFO")

    tools = tools if tools is not None else get_default_tools(model, tools_config=tools_config)
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
        tools_config=tools_config,
        profile=profile,
        customizations=customizations
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

def task(
    task: str = typer.Argument(..., help="The task to solve"),
    model: str = typer.Option(DEFAULT_MODEL, help="The litellm model to use"),
    max_iterations: int = typer.Option(5, help="Maximum reasoning steps"),
    success_criteria: str = typer.Option(None, help="Optional criteria to determine task completion"),
    personality: str = typer.Option(None, help="Agent personality (e.g., 'witty')"),
    backstory: str = typer.Option(None, help="Agent backstory"),
    sop: str = typer.Option(None, help="Standard operating procedure"),
    debug: bool = typer.Option(False, help="Enable debug logging to stderr"),
    streaming: bool = typer.Option(False, help="Enable streaming output for real-time token generation"),
    reasoner: str = typer.Option(None, help="Name of the reasoner to use"),
    executor: str = typer.Option(None, help="Name of the executor to use"),
    tools_config: str = typer.Option(None, help="JSON/YAML string for tools_config"),
    profile: str = typer.Option(None, help="Agent profile (e.g., 'math_expert')"),
    customizations: str = typer.Option(None, help="JSON/YAML string for customizations")
) -> None:
    """CLI command to run the Agent with detailed event monitoring."""
    try:
        # Parse optional JSON/YAML strings
        tools_config_list = json.loads(tools_config) if tools_config else None
        customizations_dict = json.loads(customizations) if customizations else None
        asyncio.run(run_react_agent(
            task, model, max_iterations, success_criteria,
            personality=personality, backstory=backstory, sop=sop, debug=debug,
            streaming=streaming, reasoner_name=reasoner, executor_name=executor,
            tools_config=tools_config_list, profile=profile, customizations=customizations_dict
        ))
    except Exception as e:
        logger.error(f"Agent failed: {e}")
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)