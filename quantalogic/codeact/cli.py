import asyncio
from typing import Callable, List, Optional, Union

import typer
from loguru import logger

from quantalogic.tools import create_tool

from .agent import (
    ActionExecutedEvent,
    ActionGeneratedEvent,
    ErrorOccurredEvent,
    ReActAgent,
    StepCompletedEvent,
    TaskCompletedEvent,
    TaskStartedEvent,
    ThoughtGeneratedEvent,
)
from .constants import DEFAULT_MODEL
from .tools_manager import Tool, get_default_tools

app = typer.Typer(no_args_is_help=True)

# Observer to display detailed progress for each Pydantic-based event type
async def detailed_progress_monitor(event: Union[
    TaskStartedEvent, ThoughtGeneratedEvent, ActionGeneratedEvent, ActionExecutedEvent, 
    StepCompletedEvent, ErrorOccurredEvent, TaskCompletedEvent
]) -> None:
    """Observer that displays detailed progress for various agent events."""
    if isinstance(event, TaskStartedEvent):
        typer.echo(typer.style(f"Task Started: {event.task_description}", fg=typer.colors.GREEN, bold=True))
        typer.echo(f"Timestamp: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        typer.echo("-" * 50)

    elif isinstance(event, ThoughtGeneratedEvent):
        typer.echo(typer.style(f"Step {event.step_number} - Thought Generated:", fg=typer.colors.CYAN, bold=True))
        typer.echo(f"Thought: {event.thought}")
        typer.echo(f"Generation Time: {event.generation_time:.2f} seconds")
        typer.echo("-" * 50)

    elif isinstance(event, ActionGeneratedEvent):
        typer.echo(typer.style(f"Step {event.step_number} - Action Generated:", fg=typer.colors.BLUE, bold=True))
        typer.echo(f"Action Code:\n{event.action_code}")
        typer.echo(f"Generation Time: {event.generation_time:.2f} seconds")
        typer.echo("-" * 50)

    elif isinstance(event, ActionExecutedEvent):
        typer.echo(typer.style(f"Step {event.step_number} - Action Executed:", fg=typer.colors.MAGENTA, bold=True))
        typer.echo(f"Result:\n{event.result_xml}")
        typer.echo(f"Execution Time: {event.execution_time:.2f} seconds")
        typer.echo("-" * 50)

    elif isinstance(event, StepCompletedEvent):
        typer.echo(typer.style(f"Step {event.step_number} - Completed:", fg=typer.colors.YELLOW, bold=True))
        typer.echo(f"Thought: {event.thought}")
        typer.echo(f"Action: {event.action}")
        typer.echo(f"Result: {event.result}")
        if event.is_complete:
            typer.echo(typer.style(f"Task completed with answer: {event.final_answer}", fg=typer.colors.GREEN, bold=True))
        typer.echo("-" * 50)

    elif isinstance(event, ErrorOccurredEvent):
        typer.echo(typer.style(f"Error Occurred{' at Step ' + str(event.step_number) if event.step_number else ''}:", fg=typer.colors.RED, bold=True))
        typer.echo(f"Message: {event.error_message}")
        typer.echo(f"Timestamp: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        typer.echo("-" * 50)

    elif isinstance(event, TaskCompletedEvent):
        typer.echo(typer.style("Task Completed:", fg=typer.colors.GREEN if event.reason == "success" else typer.colors.RED, bold=True))
        if event.final_answer:
            typer.echo(f"Final Answer: {event.final_answer}")
        typer.echo(f"Reason: {event.reason}")
        typer.echo(f"Timestamp: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        typer.echo("-" * 50)

async def run_react_agent(
    task: str,
    model: str,
    max_iterations: int,
    success_criteria: Optional[str] = None,
    tools: Optional[List[Union[Tool, Callable]]] = None
) -> None:
    """Run the ReActAgent with detailed event monitoring using Pydantic-based events."""
    tools = tools if tools is not None else get_default_tools(model)
    
    processed_tools = []
    for tool in tools:
        if isinstance(tool, Tool):
            processed_tools.append(tool)
        elif callable(tool):
            processed_tools.append(create_tool(tool))
        else:
            logger.warning(f"Invalid tool type: {type(tool)}. Skipping.")
            typer.echo(typer.style(f"Warning: Invalid tool type {type(tool)} skipped.", fg=typer.colors.YELLOW))

    agent = ReActAgent(model=model, tools=processed_tools, max_iterations=max_iterations)
    
    # Subscribe the observer to all event types
    event_types = [
        "TaskStarted",
        "ThoughtGenerated",
        "ActionGenerated",
        "ActionExecuted",
        "StepCompleted",
        "ErrorOccurred",
        "TaskCompleted"
    ]
    agent.add_observer(detailed_progress_monitor, event_types)
    
    typer.echo(typer.style(f"Starting task: {task}", fg=typer.colors.GREEN, bold=True))
    history = await agent.solve(task, success_criteria)
    
    # Final summary (optional, since TaskCompletedEvent already covers this)
    if history and "<FinalAnswer><![CDATA[" in history[-1]["result"]:
        start = history[-1]["result"].index("<FinalAnswer><![CDATA[") + len("<FinalAnswer><![CDATA[")
        end = history[-1]["result"].index("]]></FinalAnswer>", start)
        final_answer = history[-1]["result"][start:end].strip()
        typer.echo(f"\n{typer.style('Final Answer', fg=typer.colors.GREEN, bold=True)}")
        typer.echo(final_answer)
    elif history:
        typer.echo(typer.style("\nTask did not complete successfully.", fg=typer.colors.RED))

@app.command()
def react(
    task: str = typer.Argument(..., help="The task to solve"),
    model: str = typer.Option(DEFAULT_MODEL, help="The litellm model to use"),
    max_iterations: int = typer.Option(5, help="Maximum reasoning steps"),
    success_criteria: Optional[str] = typer.Option(None, help="Optional criteria to determine task completion"),
) -> None:
    """CLI command to run the ReActAgent with detailed event monitoring."""
    try:
        asyncio.run(run_react_agent(task, model, max_iterations, success_criteria))
    except Exception as e:
        logger.error(f"Agent failed: {e}")
        typer.echo(typer.style(f"Error: {e}", fg=typer.colors.RED))
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()