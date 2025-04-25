import asyncio
import sys
from pathlib import Path

import typer
from loguru import logger
from nanoid import generate
from rich.box import DOUBLE
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from quantalogic_codeact.codeact.agent import Agent
from quantalogic_codeact.codeact.agent_config import GLOBAL_CONFIG_PATH, AgentConfig
from quantalogic_codeact.codeact.constants import DEFAULT_MODEL, LOG_FILE
from quantalogic_codeact.codeact.events import (
    ActionExecutedEvent,
    ActionGeneratedEvent,
    ErrorOccurredEvent,
    StepCompletedEvent,
    StepStartedEvent,
    StreamTokenEvent,
    TaskCompletedEvent,
    TaskStartedEvent,
    ThoughtGeneratedEvent,
    ToolConfirmationRequestEvent,
    ToolConfirmationResponseEvent,
    ToolExecutionCompletedEvent,
    ToolExecutionErrorEvent,
    ToolExecutionStartedEvent,
)
from quantalogic_codeact.codeact.personality_config import PersonalityConfig
from quantalogic_codeact.codeact.tools_manager import get_default_tools
from quantalogic_codeact.codeact.xml_utils import XMLResultHandler

console = Console()

class ProgressMonitor:
    """Handles progress monitoring for agent events."""
    def __init__(self):
        self._token_buffer = ""
        self.agent = None
        self.confirmation_future = None

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
        console.print(f"[bold red]Tool {event.tool_name} execution error at step {event.step_number}[/bold red]")
        console.print(f"Error: {event.error}")

    async def on_tool_confirmation_request(self, event: ToolConfirmationRequestEvent):
        # Format parameter display nicely
        param_display = "\n".join([f"  - {k}: {v}" for k, v in event.parameters_summary.items()])
        
        # Show confirmation prompt with rich formatting
        console.print(Panel(
            f"Tool: {event.tool_name}\nParameters:\n{param_display}\n\n{event.confirmation_message}",
            title="[bold yellow]Confirmation Required[/bold yellow]",
            border_style="yellow"
        ))
        
        # Store the confirmation_future for later use
        self.confirmation_future = getattr(event, 'confirmation_future', None)
        
        # Ask for explicit confirmation in CLI mode
        if hasattr(self, 'agent') and self.agent and hasattr(self.agent, 'react_agent'):
            while True:
                response = input("Confirm (yes/no): ").strip().lower()
                if response in ('y', 'yes'):
                    confirm = True
                    break
                elif response in ('n', 'no'):
                    confirm = False
                    break
                console.print("[red]Please enter 'yes' or 'no'[/red]")
            
            # Log the confirmation response
            if confirm:
                console.print(f"[green]Confirmed execution of {event.tool_name}[/green]")
            else:
                console.print(f"[red]Cancelled execution of {event.tool_name}[/red]")
                
            # Directly set the result on the future to unblock execution
            if self.confirmation_future and not self.confirmation_future.done():
                self.confirmation_future.set_result(confirm)
            else:
                logger.warning("Could not resolve confirmation future properly")

    async def on_tool_confirmation_response(self, event: ToolConfirmationResponseEvent):
        # This event is typically generated after the confirmation is handled
        # We should only display the message without trying to resolve the future again
        if event.confirmed:
            console.print(f"[green]Confirmation response received for {event.tool_name}[/green]")
        else:
            console.print(f"[red]Cancellation response received for {event.tool_name}[/red]")

    async def on_stream_token(self, event: StreamTokenEvent):
        self._token_buffer += event.token

    async def flush_buffer(self):
        console.print(self._token_buffer, end="")
        self._token_buffer = ""

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
        elif isinstance(event, ToolConfirmationRequestEvent):
            await self.on_tool_confirmation_request(event)
        elif isinstance(event, ToolConfirmationResponseEvent):
            await self.on_tool_confirmation_response(event)
        elif isinstance(event, StreamTokenEvent):
            await self.on_stream_token(event)

async def run_react_agent(
    task: str,
    agent_config: AgentConfig,  # Use passed AgentConfig
    success_criteria: str = None,
    tools=None,
    personality_config: PersonalityConfig = None,
    debug: bool = False,
    streaming: bool = False,
    reasoner_name=None,
    executor_name=None,
    tools_config=None,
    task_id: str = None,
) -> None:
    """Run the Agent with detailed event monitoring.
    
    Args:
        task: The task to solve.
        agent_config: Configuration for the agent.
        success_criteria: Optional criteria to determine task completion.
        tools: Optional list of custom tools.
        personality_config: Optional personality configuration.
        debug: Enable debug logging.
        streaming: Enable streaming output for real-time token generation.
        reasoner_name: Optional name of the reasoner to use.
        executor_name: Optional name of the executor to use.
        tools_config: Optional tools configuration.
        task_id: Unique ID to group related events. If None, a default ID will be generated.
    """
    # Use log_level from agent_config by default, but override with DEBUG if debug flag is True
    log_level = "DEBUG" if debug else agent_config.log_level
    
    logger.remove()
    logger.add(sys.stderr, level=log_level)
    logger.add(LOG_FILE, level=log_level)
    
    # Get default tools if none provided
    tools = tools if tools is not None else get_default_tools(agent_config.model)

    # Update AgentConfig with CLI-provided values
    if personality_config:
        agent_config.personality = personality_config
    agent_config.reasoner_name = reasoner_name or agent_config.reasoner_name
    agent_config.executor_name = executor_name or agent_config.executor_name
    
    agent = Agent(config=agent_config)
    
    progress_monitor = ProgressMonitor()
    progress_monitor.agent = agent  # Set the agent reference for confirmation handling
    solve_agent = agent
    solve_agent.add_observer(progress_monitor, [
        "TaskStarted", "ThoughtGenerated", "ActionGenerated", "ActionExecuted",
        "StepCompleted", "ErrorOccurred", "TaskCompleted", "StepStarted",
        "ToolExecutionStarted", "ToolExecutionCompleted", "ToolExecutionError",
        "ToolConfirmationRequest", "ToolConfirmationResponse",
        "StreamToken"
    ])
    
    # Generate a default task_id if none is provided
    if task_id is None:
        task_id = generate(size=21)
        
    console.print(f"[bold green]Starting task: {task}[/bold green]")
    console.print(f"[dim]Task ID: {task_id}[/dim]")
    _history = await agent.solve(task, success_criteria, streaming=streaming,
                                reasoner_name=reasoner_name, executor_name=executor_name,
                                task_id=task_id)

def task(
    ctx: typer.Context,
    task: str = typer.Argument(..., help="The task to solve"),
    model: str = typer.Option(DEFAULT_MODEL, help="The litellm model to use"),
    max_iterations: int = typer.Option(5, help="Maximum reasoning steps"),
    success_criteria: str = typer.Option(None, help="Optional criteria to determine task completion"),
    system: str = typer.Option(None, help="System prompt for personality behavior"),
    adjectives: str = typer.Option(None, help="Comma-separated list of personality adjectives"),
    bio: str = typer.Option(None, help="Backstory/biography for the agent"),
    sop: str = typer.Option(None, help="Standard Operating Procedure that must be strictly followed"),
    debug: bool = typer.Option(False, help="Enable debug logging to stderr"),
    streaming: bool = typer.Option(False, help="Enable streaming output for real-time token generation"),
    reasoner: str = typer.Option(None, help="Name of the reasoner to use"),
    executor: str = typer.Option(None, help="Name of the executor to use"),
    tools_config: str = typer.Option(None, help="JSON/YAML string for tools_config"),
    temperature: float = typer.Option(0.7, help="Temperature for the language model (0 to 1)"),
    task_id: str = typer.Option(None, help="Optional unique ID to group related events")
) -> None:
    """CLI command to run the Agent with detailed event monitoring."""
    try:
        # Get AgentConfig from context or load from file (same as shell.py)
        agent_config = ctx.obj.get("agent_config") or AgentConfig.load_from_file(GLOBAL_CONFIG_PATH)
        
        # Ensure config is properly initialized with required fields
        agent_config = AgentConfig.ensure_initialized(agent_config)
            
        # Create default config file if it doesn't exist
        config_path = Path(GLOBAL_CONFIG_PATH)
        if not config_path.exists():
            try:
                logger.info(f"Creating default configuration file at {config_path}")
                agent_config.save_to_file(str(config_path))
            except Exception as e:
                logger.error(f"Failed to create default config file: {e}")
        
        # Update with CLI-provided values
        updated_config = agent_config.copy(deep=True)
        updated_config.model = model
        updated_config.max_iterations = max_iterations
        updated_config.temperature = temperature
        
        # Create PersonalityConfig from CLI arguments if any are provided
        personality_config = None
        if system or adjectives or bio or sop:
            personality_config = PersonalityConfig(
                system=system or "",
                adjectives=adjectives.split(",") if adjectives else [],
                bio=[bio] if bio else [],
                sop=sop or ""
            )
            
        asyncio.run(run_react_agent(
            task, updated_config, success_criteria,
            personality_config=personality_config, debug=debug,
            streaming=streaming, reasoner_name=reasoner, executor_name=executor,
            tools_config=tools_config, task_id=task_id
        ))
    except Exception as e:
        logger.error(f"Agent failed: {e}")
        console.print(Panel(
            Text(repr(e), style="red"),
            title="[bold red]Task did not complete successfully[/bold red]",
            box=DOUBLE, expand=True
        ))
        raise typer.Exit(code=1)