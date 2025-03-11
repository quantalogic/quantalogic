"""Task runner module for executing tasks with the QuantaLogic AI Assistant."""

import sys
from threading import Lock
from typing import Any, Callable, Optional, Set

from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from quantalogic.agent_factory import AgentRegistry, create_agent_for_mode
from quantalogic.config import QLConfig
from quantalogic.console_print_events import console_print_events
from quantalogic.interactive_text_editor import get_multiline_input
from quantalogic.task_file_reader import get_task_from_file
from quantalogic.version_check import check_new_version, get_version
from quantalogic.welcome_message import display_welcome_message

# Spinner and console output control
spinner_lock = Lock()
console_lock = Lock()
current_spinner = None
processed_chunks: Set[str] = set()


def configure_logger(log_level: str) -> None:
    """Configure the logger with the specified log level and format."""
    logger.add(
        sys.stderr,
        level=log_level.upper(),
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{process}</cyan> | <magenta>{file}:{line}</magenta> | {message}",
    )
    logger.debug(f"Log level set to: {log_level}")


def set_litellm_verbose(verbose_mode: bool) -> None:
    """Set the verbosity of the litellm library."""
    import litellm
    litellm.set_verbose = verbose_mode


def switch_verbose(verbose_mode: bool, log_level: str = "info") -> None:
    """Switch verbose mode and configure logger and litellm verbosity."""
    if log_level == "debug":
        configure_logger("DEBUG")
    else:
        configure_logger(log_level)
    
    verbose_mode = verbose_mode if verbose_mode is not None else False
    set_litellm_verbose(verbose_mode)
    logger.debug(f"litellm verbose mode set to: {verbose_mode}")


def start_spinner(console: Console, message: str = "[yellow]Thinking...[/yellow]") -> None:
    """Start the spinner with a custom message.
    
    Args:
        console: The Rich console instance
        message: Custom message to display with the spinner (default: "Thinking...")
    """
    global current_spinner
    with spinner_lock:
        if current_spinner is None:
            current_spinner = console.status(message, spinner="dots")
            current_spinner.start()


def stop_spinner(console: Console) -> None:
    """Stop the thinking spinner."""
    global current_spinner
    with spinner_lock:
        if current_spinner is not None:
            current_spinner.stop()
            current_spinner = None


def register_spinner_handlers(agent, console: Console) -> None:
    """Register common spinner control handlers."""
    def handle_think_start(*args, **kwargs):
        if current_spinner:
            stop_spinner(console)
        start_spinner(console)

    def handle_think_end(*args, **kwargs):
        stop_spinner(console)

    agent.event_emitter.on("task_think_start", handle_think_start)
    agent.event_emitter.on("task_think_end", handle_think_end)


def create_stream_handler(console: Console) -> Callable:
    """Create a handler for streaming chunks that works across all modes."""
    def handle_stream_chunk(event: str, data: Any) -> None:
        if current_spinner:
            stop_spinner(console)
        
        if data is None:
            return
            
        # Extract content from various data formats
        if isinstance(data, str):
            content = data
        elif isinstance(data, dict) and "data" in data:
            content = data["data"]
        elif isinstance(data, dict):
            logger.debug(f"Stream chunk data without 'data' key: {data}")
            content = str(data)
        else:
            try:
                content = str(data)
            except Exception as e:
                logger.error(f"Error processing stream chunk: {e}")
                return

        # Print content with thread safety
        with console_lock:
            console.print(content, end="", markup=False)
            
    return handle_stream_chunk


def run_chat_mode(agent, console: Console, config: QLConfig) -> None:
    """Run the assistant in chat mode."""
    console.print(f"[green]Entering chat mode with persona: {config.chat_system_prompt}[/green]")
    if config.tool_mode:
        console.print(f"[green]Tool mode: {config.tool_mode}[/green]")
    console.print("[yellow]Type '/exit' to quit or '/clear' to reset memory.[/yellow]")

    # Event handlers specific to chat mode
    def handle_chat_start(*args, **kwargs):
        start_spinner(console) # Uses default "Thinking..." message
        console.print("Assistant: ", end="")

    def handle_chat_response(*args, **kwargs):
        # Always stop any active spinner (whether from tool execution or thinking)
        stop_spinner(console)
        
        if "response" in kwargs:
            # Get the response from the kwargs
            response_text = kwargs["response"]
            
            # Simply print the response text without special tool call handling
            console.print(response_text)

    def handle_chat_end(*args, **kwargs):
        # This function is intentionally empty as we're handling the prompt in the main loop
        pass
        
    def handle_tool_execution_start(*args, **kwargs):
        # Print a newline before tool execution starts
        console.print("\n")
        # Start a spinner to indicate tool execution is in progress
        tool_name = kwargs.get("tool_name", "tool")
        start_spinner(console, f"[yellow]Executing {tool_name}...[/yellow]")
        
    def handle_tool_execution_end(*args, **kwargs):
        # Stop the tool execution spinner
        stop_spinner(console)
        # Start a thinking spinner to indicate the agent is processing the tool results
        start_spinner(console, "[yellow]Processing tool results...[/yellow]")

    # Register chat-specific handlers
    agent.event_emitter.on("chat_start", handle_chat_start)
    agent.event_emitter.on("chat_end", handle_chat_end)
    agent.event_emitter.on("chat_response", handle_chat_response)
    
    # Register tool execution handlers for newlines
    agent.event_emitter.on("tool_execution_start", handle_tool_execution_start)
    agent.event_emitter.on("tool_execution_end", handle_tool_execution_end)
    
    # First clear any existing handlers to prevent duplicates
    agent.event_emitter.clear("stream_chunk")
    
    # Register ONLY ONE stream handler for chat mode (fix for token duplication)
    agent.event_emitter.on("stream_chunk", create_stream_handler(console))

    try:
        while True:
            # Add a newline before the prompt for better readability, except on the first iteration
            if agent.memory.memory and len(agent.memory.memory) > 1:  # Check if we have any conversation history
                console.print("")
            
            user_input = console.input("You: ")
            if user_input.lower() == "/exit":
                console.print("[yellow]Exiting chat mode.[/yellow]")
                # Emit the chat_end event before exiting
                agent.event_emitter.emit("chat_end")
                break
            elif user_input.lower() == "/clear":
                agent.clear_memory()
                console.print("[green]Chat memory cleared.[/green]")
                continue
            
            try:
                response = agent.chat(user_input, streaming=not config.no_stream)
                # For non-streaming mode, we need to manually emit the chat_response event
                # since it won't be triggered by the streaming handler
                if config.no_stream and response:
                    agent.event_emitter.emit("chat_response", response=response)
            except Exception as e:
                stop_spinner(console)
                console.print(f"[red]Error: {str(e)}[/red]")
                logger.error(f"Chat error: {e}", exc_info=True)
    except KeyboardInterrupt:
        console.print("\n[yellow]Chat interrupted. Exiting chat mode.[/yellow]")
        # Emit the chat_end event when interrupted with Ctrl+C
        agent.event_emitter.emit("chat_end")


def run_file_mode(agent, console: Console, file: str, config: QLConfig) -> None:
    """Run a task from a file."""
    task_content = get_task_from_file(file)
    
    # Clear any existing handlers to prevent duplicates
    agent.event_emitter.clear("stream_chunk")
    
    # Register stream handler
    agent.event_emitter.on("stream_chunk", create_stream_handler(console))
    
    # Execute task from file
    logger.debug(f"Solving task with agent: {task_content}")
    if config.max_iterations < 1:
        raise ValueError("max_iterations must be greater than 0")
        
    result = agent.solve_task(
        task=task_content,
        max_iterations=config.max_iterations,
        streaming=not config.no_stream
    )
    
    logger.debug(f"Task solved with result: {result} using {config.max_iterations} iterations")
    console.print(
        Panel.fit(
            f"[bold]Task Result:[/bold]\n{result}",
            title="[bold]Execution Output[/bold]",
            border_style="green"
        )
    )


def run_task_mode(agent, console: Console, task: str, config: QLConfig) -> None:
    """Run a single task from command line."""
    check_new_version()
    
    # Clear any existing handlers to prevent duplicates
    agent.event_emitter.clear("stream_chunk")
    
    # Register stream handler
    agent.event_emitter.on("stream_chunk", create_stream_handler(console))
    
    # Execute task from command line
    logger.debug(f"Solving task with agent: {task}")
    if config.max_iterations < 1:
        raise ValueError("max_iterations must be greater than 0")
        
    result = agent.solve_task(
        task=task,
        max_iterations=config.max_iterations,
        streaming=not config.no_stream
    )
    
    logger.debug(f"Task solved with result: {result} using {config.max_iterations} iterations")
    console.print(
        Panel.fit(
            f"[bold]Task Result:[/bold]\n{result}",
            title="[bold]Execution Output[/bold]",
            border_style="green"
        )
    )


def process_interactive_command(
    command: str,
    agent,
    console: Console
) -> bool:
    """Process interactive commands and return whether to continue."""
    if command == "/clear":
        logger.info("Clearing agent memory...")
        console.print("[yellow]Clearing agent memory...[/yellow]")
        agent.clear_memory()
        console.print("[green]Memory cleared successfully![/green]")
        return True
    else:
        console.print(f"[red]Unknown command: {command}[/red]")
        return True


def handle_interactive_task(
    agent,
    console: Console,
    task_content: str,
    max_iterations: int,
    no_stream: bool
) -> None:
    """Handle a single interactive task."""
    console.print(
        Panel.fit(
            f"[bold]Task to be submitted:[/bold]\n{task_content}",
            title="[bold]Task Preview[/bold]",
            border_style="blue",
        )
    )

    if not Confirm.ask("[bold]Are you sure you want to submit this task?[/bold]"):
        console.print("[yellow]Task submission cancelled.[/yellow]")
        return

    console.print(
        Panel.fit(
            "[green]✓ Task successfully submitted! Processing...[/green]",
            title="[bold]Status[/bold]",
            border_style="green",
        )
    )

    logger.debug(f"Solving task with agent: {task_content}")
    result = agent.solve_task(
        task=task_content,
        max_iterations=max_iterations,
        streaming=not no_stream,
        clear_memory=False
    )
    
    logger.debug(f"Task solved with result: {result} using {max_iterations} iterations")
    console.print(
        Panel.fit(
            f"[bold]Task Result:[/bold]\n{result}",
            title="[bold]Execution Output[/bold]",
            border_style="green"
        )
    )


def interactive_task_runner(
    agent,
    console: Console,
    max_iterations: int,
    no_stream: bool,
) -> None:
    """Run tasks interactively, asking the user if they want to continue after each task."""
    while True:
        logger.debug("Waiting for user input...")
        task_content = get_multiline_input(console).strip()

        if not task_content:
            logger.info("No task provided. Exiting...")
            console.print("[yellow]No task provided. Exiting...[/yellow]")
            break

        # Handle commands
        if task_content.startswith("/"):
            if not process_interactive_command(task_content.lower(), agent, console):
                break
            continue

        # Handle regular task
        handle_interactive_task(agent, console, task_content, max_iterations, no_stream)
        
        if not Confirm.ask("[bold]Would you like to ask another question?[/bold]"):
            break


def run_interactive_mode(agent, console: Console, config: QLConfig) -> None:
    """Run the assistant in interactive mode."""
    display_welcome_message(
        console=console,
        model_name=config.model_name,
        version=get_version(),
        vision_model_name=config.vision_model_name,
        max_iterations=config.max_iterations,
        compact_every_n_iteration=config.compact_every_n_iteration,
        max_tokens_working_memory=config.max_tokens_working_memory,
        mode=config.mode,
    )
    check_new_version()
    
    logger.debug(
        f"Created agent for mode: {config.mode} with model: {config.model_name}, "
        f"vision model: {config.vision_model_name}, no_stream: {config.no_stream}"
    )

    # Register event handlers for interactive mode
    events = [
        "task_start", "task_think_start", "task_think_end", "task_complete",
        "tool_execution_start", "tool_execution_end", "error_max_iterations_reached",
        "memory_full", "memory_compacted", "memory_summary",
    ]
    
    agent.event_emitter.on(event=events, listener=console_print_events)
    
    # Clear any existing handlers to prevent duplicates
    agent.event_emitter.clear("stream_chunk")
    
    # Register stream handler
    agent.event_emitter.on("stream_chunk", create_stream_handler(console))

    logger.debug(f"Registered event handlers for agent events with events: {events}")
    interactive_task_runner(agent, console, config.max_iterations, config.no_stream)


def task_runner(
    console: Console,
    file: Optional[str],
    config: QLConfig,
    task: Optional[str],
) -> None:
    """Execute a task or chat with the QuantaLogic AI Assistant."""
    switch_verbose(
        config.verbose if hasattr(config, 'verbose') else False,
        config.log
    )

    # Create the agent instance with the specified configuration
    agent = create_agent_for_mode(
        mode=config.mode,
        model_name=config.model_name,
        vision_model_name=config.vision_model_name,
        thinking_model_name=config.thinking_model_name,
        compact_every_n_iteration=config.compact_every_n_iteration,
        max_tokens_working_memory=config.max_tokens_working_memory,
        chat_system_prompt=config.chat_system_prompt,
        tool_mode=config.tool_mode,
    )

    AgentRegistry.register_agent("main_agent", agent)
    register_spinner_handlers(agent, console)

    # Dispatch to the appropriate mode runner
    if config.mode == "chat":
        run_chat_mode(agent, console, config)
        # Print the final prompt with backslash when exiting chat mode
        print("You:\\")
    elif file:
        run_file_mode(agent, console, file, config)
    elif task:
        run_task_mode(agent, console, task, config)
    else:
        run_interactive_mode(agent, console, config)