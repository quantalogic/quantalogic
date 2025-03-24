import asyncio
from typing import Callable, List, Optional, Union

import typer
from loguru import logger

from quantalogic.tools import create_tool

from .agent import Agent  # Import only Agent from agent.py
from .constants import DEFAULT_MODEL, LOG_FILE
from .events import (  # Import events from events.py
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
from .tools_manager import Tool, get_default_tools
from .utils import XMLResultHandler

app = typer.Typer(no_args_is_help=True)

class ProgressMonitor:
    """Handles progress monitoring for agent events."""
    def __init__(self):
        self._token_buffer = ""  # Buffer to accumulate streaming tokens

    async def on_task_started(self, event: TaskStartedEvent):
        typer.echo(typer.style(f"Task Started: {event.task_description}", fg=typer.colors.GREEN, bold=True))
        typer.echo(f"Timestamp: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        typer.echo("-" * 50)

    async def on_thought_generated(self, event: ThoughtGeneratedEvent):
        typer.echo(typer.style(f"Step {event.step_number} - Thought Generated:", fg=typer.colors.CYAN, bold=True))
        typer.echo(f"Thought: {event.thought}")
        typer.echo(f"Generation Time: {event.generation_time:.2f} seconds")
        typer.echo("-" * 50)

    async def on_action_generated(self, event: ActionGeneratedEvent):
        typer.echo(typer.style(f"Step {event.step_number} - Action Generated:", fg=typer.colors.BLUE, bold=True))
        typer.echo(f"Action Code:\n{event.action_code}")
        typer.echo(f"Generation Time: {event.generation_time:.2f} seconds")
        typer.echo("-" * 50)

    async def on_action_executed(self, event: ActionExecutedEvent):
        summary = XMLResultHandler.format_result_summary(event.result_xml)
        typer.echo(typer.style(f"Step {event.step_number} - Action Executed:", fg=typer.colors.MAGENTA, bold=True))
        typer.echo(f"Result Summary:\n{summary}")
        typer.echo(f"Execution Time: {event.execution_time:.2f} seconds")
        typer.echo("-" * 50)

    async def on_step_completed(self, event: StepCompletedEvent):
        typer.echo(typer.style(f"Step {event.step_number} - Completed", fg=typer.colors.YELLOW, bold=True))
        typer.echo("-" * 50)

    async def on_error_occurred(self, event: ErrorOccurredEvent):
        typer.echo(typer.style(f"Error Occurred{' at Step ' + str(event.step_number) if event.step_number else ''}:", fg=typer.colors.RED, bold=True))
        typer.echo(f"Message: {event.error_message}")
        typer.echo(f"Timestamp: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        typer.echo("-" * 50)

    async def on_task_completed(self, event: TaskCompletedEvent):
        if event.final_answer:
            typer.echo(typer.style("Task Completed Successfully:", fg=typer.colors.GREEN, bold=True))
            typer.echo(f"Final Answer:\n{event.final_answer}")
        else:
            typer.echo(typer.style("Task Did Not Complete Successfully:", fg=typer.colors.RED, bold=True))
            typer.echo(f"Reason: {event.reason}")
        typer.echo(f"Timestamp: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        typer.echo("-" * 50)

    async def on_step_started(self, event: StepStartedEvent):
        typer.echo(typer.style(f"Starting Step {event.step_number}", fg=typer.colors.YELLOW, bold=True))
        typer.echo("-" * 50)

    async def on_tool_execution_started(self, event: ToolExecutionStartedEvent):
        typer.echo(typer.style(f"Tool {event.tool_name} started execution at step {event.step_number}", fg=typer.colors.CYAN))
        typer.echo(f"Parameters: {event.parameters_summary}")

    async def on_tool_execution_completed(self, event: ToolExecutionCompletedEvent):
        typer.echo(typer.style(f"Tool {event.tool_name} completed execution at step {event.step_number}", fg=typer.colors.GREEN))
        typer.echo(f"Result: {event.result_summary}")

    async def on_tool_execution_error(self, event: ToolExecutionErrorEvent):
        typer.echo(typer.style(f"Tool {event.tool_name} encountered an error at step {event.step_number}", fg=typer.colors.RED))
        typer.echo(f"Error: {event.error}")

    async def on_stream_token(self, event: StreamTokenEvent):
        """Handle streaming token events for real-time output with buffering."""
        self._token_buffer += event.token
        # Check for natural breakpoints to flush the buffer
        if "\n" in event.token or event.token.strip() in [".", ";", ":", "{", "}", "]", ")"]:
            # Print the accumulated buffer with proper formatting
            lines = self._token_buffer.split("\n")
            for line in lines[:-1]:  # Print all complete lines
                if line.strip():
                    typer.echo(f"{line}", nl=False)
                    typer.echo("")  # Add newline after each complete line
            # Keep the last incomplete line in the buffer
            self._token_buffer = lines[-1]
        # Flush buffer if it gets too long (e.g., > 100 chars)
        if len(self._token_buffer) > 100:
            typer.echo(f"{self._token_buffer}", nl=False)
            self._token_buffer = ""

    async def flush_buffer(self):
        """Flush any remaining tokens in the buffer."""
        if self._token_buffer.strip():
            typer.echo(f"{self._token_buffer}")
            self._token_buffer = ""

    async def __call__(self, event):
        """Dispatch events to their respective handlers."""
        if isinstance(event, TaskStartedEvent):
            await self.on_task_started(event)
        elif isinstance(event, ThoughtGeneratedEvent):
            await self.on_thought_generated(event)
        elif isinstance(event, ActionGeneratedEvent):
            await self.on_action_generated(event)
            await self.flush_buffer()  # Flush after action is fully generated
        elif isinstance(event, ActionExecutedEvent):
            await self.on_action_executed(event)
        elif isinstance(event, StepCompletedEvent):
            await self.on_step_completed(event)
        elif isinstance(event, ErrorOccurredEvent):
            await self.on_error_occurred(event)
        elif isinstance(event, TaskCompletedEvent):
            await self.on_task_completed(event)
            await self.flush_buffer()  # Flush at task completion
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
    streaming: bool = False  # New parameter for enabling streaming
) -> None:
    """Run the Agent with detailed event monitoring."""
    # Configure logging: disable stderr output unless debug is enabled
    logger.remove()  # Remove default handler
    if debug:
        logger.add(typer.stderr, level="INFO")
    logger.add(LOG_FILE, level="INFO")  # Always log to file

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

    agent = Agent(
        model=model,
        tools=processed_tools,
        max_iterations=max_iterations,
        personality=personality,
        backstory=backstory,
        sop=sop
    )
    
    progress_monitor = ProgressMonitor()
    # Use solve with tools enabled for multi-step tasks
    solve_agent = agent  # Store reference to add observer
    solve_agent.add_observer(progress_monitor, [
        "TaskStarted", "ThoughtGenerated", "ActionGenerated", "ActionExecuted",
        "StepCompleted", "ErrorOccurred", "TaskCompleted", "StepStarted",
        "ToolExecutionStarted", "ToolExecutionCompleted", "ToolExecutionError",
        "StreamToken"  # Added to observe streaming tokens
    ])
    
    typer.echo(typer.style(f"Starting task: {task}", fg=typer.colors.GREEN, bold=True))
    # Pass the streaming flag to the solve method
    history = await agent.solve(task, success_criteria, streaming=streaming)

@app.command()
def react(
    task: str = typer.Argument(..., help="The task to solve"),
    model: str = typer.Option(DEFAULT_MODEL, help="The litellm model to use"),
    max_iterations: int = typer.Option(5, help="Maximum reasoning steps"),
    success_criteria: Optional[str] = typer.Option(None, help="Optional criteria to determine task completion"),
    personality: Optional[str] = typer.Option(None, help="Agent personality (e.g., 'witty')"),
    backstory: Optional[str] = typer.Option(None, help="Agent backstory"),
    sop: Optional[str] = typer.Option(None, help="Standard operating procedure"),
    debug: bool = typer.Option(False, help="Enable debug logging to stderr"),
    streaming: bool = typer.Option(False, help="Enable streaming output for real-time token generation")
) -> None:
    """CLI command to run the Agent with detailed event monitoring."""
    try:
        asyncio.run(run_react_agent(
            task, model, max_iterations, success_criteria,
            personality=personality, backstory=backstory, sop=sop, debug=debug,
            streaming=streaming  # Pass the streaming flag
        ))
    except Exception as e:
        logger.error(f"Agent failed: {e}")
        typer.echo(typer.style(f"Error: {e}", fg=typer.colors.RED))
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()


# Example how to use the CLI
# python -m quantalogic.codeact.cli "Write a poem, then evaluate the quality, in French, afficher le poem et la critique. Tout doit être Français. Si le poême n'est pas de bonne qualité, ré-écrit le poême"    --streaming

