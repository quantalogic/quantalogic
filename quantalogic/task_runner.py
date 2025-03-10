"""Task runner module for executing tasks with the QuantaLogic AI Assistant."""

import sys
from threading import Lock
from typing import Any, Optional, Set

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

    # Ensure verbose_mode defaults to False if not explicitly set
    verbose_mode = verbose_mode if verbose_mode is not None else False
    set_litellm_verbose(verbose_mode)
    logger.debug(f"litellm verbose mode set to: {verbose_mode}")


def start_spinner(console: Console) -> None:
    """Start the thinking spinner."""
    global current_spinner
    with spinner_lock:
        if current_spinner is None:
            current_spinner = console.status("[yellow]Thinking...", spinner="dots")
            current_spinner.start()


def stop_spinner(console: Console) -> None:
    """Stop the thinking spinner."""
    global current_spinner
    with spinner_lock:
        if current_spinner is not None:
            current_spinner.stop()
            current_spinner = None


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

        # Handle commands with single return
        if task_content.startswith("/"):
            command = task_content.lower()
            if command == "/clear":
                logger.info("Clearing agent memory...")
                console.print("[yellow]Clearing agent memory...[/yellow]")
                agent.clear_memory()
                console.print("[green]Memory cleared successfully![/green]")
                continue
            else:
                console.print(f"[red]Unknown command: {command}[/red]")
                continue

        # For non-commands, ask for confirmation
        console.print(
            Panel.fit(
                f"[bold]Task to be submitted:[/bold]\n{task_content}",
                title="[bold]Task Preview[/bold]",
                border_style="blue",
            )
        )

        if not Confirm.ask("[bold]Are you sure you want to submit this task?[/bold]"):
            console.print("[yellow]Task submission cancelled.[/yellow]")
            if not Confirm.ask("[bold]Would you like to ask another question?[/bold]"):
                break
            continue

        console.print(
            Panel.fit(
                "[green]✓ Task successfully submitted! Processing...[/green]",
                title="[bold]Status[/bold]",
                border_style="green",
            )
        )

        logger.debug(f"Solving task with agent: {task_content}")
        result = agent.solve_task(
            task=task_content, max_iterations=max_iterations, streaming=not no_stream, clear_memory=False
        )
        logger.debug(f"Task solved with result: {result} using {max_iterations} iterations")

        console.print(
            Panel.fit(
                f"[bold]Task Result:[/bold]\n{result}", title="[bold]Execution Output[/bold]", border_style="green"
            )
        )

        if not Confirm.ask("[bold]Would you like to ask another question?[/bold]"):
            break


def task_runner(
    console: Console,
    file: Optional[str],
    config: QLConfig,
    task: Optional[str],
) -> None:
    """Execute a task or chat with the QuantaLogic AI Assistant."""
    switch_verbose(config.verbose if hasattr(config, 'verbose') else False, config.log)

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

    # IMPORTANT: Clear any existing stream_chunk handlers before adding our own
    # This prevents multiple handlers from being active simultaneously
    agent.event_emitter.clear("stream_chunk")

    # Common spinner control handlers used by all modes
    def handle_task_think_start(*args, **kwargs):
        start_spinner(console)

    def handle_task_think_end(*args, **kwargs):
        stop_spinner(console)

    # Always register spinner handlers
    agent.event_emitter.on("task_think_start", handle_task_think_start)
    agent.event_emitter.on("task_think_end", handle_task_think_end)

    # CHAT MODE
    if config.mode == "chat":
        console.print(f"[green]Entering chat mode with persona: {config.chat_system_prompt}[/green]")
        if config.tool_mode:
            console.print(f"[green]Tool mode: {config.tool_mode}[/green]")
        console.print("[yellow]Type '/exit' to quit or '/clear' to reset memory.[/yellow]")

        # Event handlers specific to chat mode
        def handle_chat_start(*args, **kwargs):
            start_spinner(console)
            console.print("Assistant: ", end="")  # Prompt for output

        def handle_chat_response(*args, **kwargs):
            stop_spinner(console)
            # In non-streaming mode, response is in kwargs
            if "response" in kwargs:
                console.print(kwargs["response"])

        def handle_chat_stream_chunk(event: str, data: Any) -> None:
            """Stream chunk handler for chat mode - prints tokens as they arrive."""
            if data is None:
                return

            # Stop spinner when first chunk arrives
            if current_spinner:
                stop_spinner(console)

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

            # Print the token immediately with thread safety
            with console_lock:
                console.print(content, end="", markup=False)

        # Register chat-specific handlers
        agent.event_emitter.on("chat_start", handle_chat_start)
        agent.event_emitter.on("chat_response", handle_chat_response)
        agent.event_emitter.on("stream_chunk", handle_chat_stream_chunk)

        while True:
            user_input = console.input("You: ")
            if user_input.lower() == "/exit":
                console.print("[yellow]Exiting chat mode.[/yellow]")
                break
            elif user_input.lower() == "/clear":
                agent.clear_memory()
                console.print("[green]Chat memory cleared.[/green]")
                continue
            try:
                response = agent.chat(user_input, streaming=not config.no_stream)
                if config.no_stream:
                    # Non-streaming: print directly (handled by handle_chat_response)
                    pass
                else:
                    # Streaming: ensure a newline after completion using once
                    agent.event_emitter.once("chat_response", lambda *args, **kwargs: console.print(""))
            except Exception as e:
                stop_spinner(console)
                console.print(f"[red]Error: {str(e)}[/red]")
                logger.error(f"Chat error: {e}", exc_info=True)

    # FILE MODE
    elif file:
        task_content = get_task_from_file(file)
        
        # Stream handler for non-chat modes
        def handle_task_stream_chunk(event: str, data: any) -> None:
            """Stream chunk handler for task mode - prints directly."""
            if current_spinner:
                stop_spinner(console)
            
            # Handle different data formats
            if data is None:
                return
            elif isinstance(data, str):
                # Direct string data
                console.print(data, end="", markup=False)
            elif isinstance(data, dict) and "data" in data:
                # Dictionary with 'data' key
                console.print(data["data"], end="", markup=False)
            elif isinstance(data, dict):
                # Dictionary without 'data' key, use the str representation
                logger.debug(f"Stream chunk data without 'data' key: {data}")
                console.print(str(data), end="", markup=False)
            else:
                # Fallback for any other type
                try:
                    console.print(str(data), end="", markup=False)
                except Exception as e:
                    logger.error(f"Error printing stream chunk: {e}")
        
        # Register task stream handler
        agent.event_emitter.on("stream_chunk", handle_task_stream_chunk)
        
        # Execute single task from file
        logger.debug(f"Solving task with agent: {task_content}")
        if config.max_iterations < 1:
            raise ValueError("max_iterations must be greater than 0")
        result = agent.solve_task(
            task=task_content, max_iterations=config.max_iterations, streaming=not config.no_stream
        )
        logger.debug(f"Task solved with result: {result} using {config.max_iterations} iterations")

        console.print(
            Panel.fit(
                f"[bold]Task Result:[/bold]\n{result}", title="[bold]Execution Output[/bold]", border_style="green"
            )
        )

    # TASK MODE (single command-line task)
    elif task:
        check_new_version()
        task_content = task
        
        # Stream handler for non-chat modes
        def handle_task_stream_chunk(event: str, data: any) -> None:
            """Stream chunk handler for task mode - prints directly."""
            if current_spinner:
                stop_spinner(console)
            
            # Handle different data formats
            if data is None:
                return
            elif isinstance(data, str):
                # Direct string data
                console.print(data, end="", markup=False)
            elif isinstance(data, dict) and "data" in data:
                # Dictionary with 'data' key
                console.print(data["data"], end="", markup=False)
            elif isinstance(data, dict):
                # Dictionary without 'data' key, use the str representation
                logger.debug(f"Stream chunk data without 'data' key: {data}")
                console.print(str(data), end="", markup=False)
            else:
                # Fallback for any other type
                try:
                    console.print(str(data), end="", markup=False)
                except Exception as e:
                    logger.error(f"Error printing stream chunk: {e}")
        
        # Register task stream handler
        agent.event_emitter.on("stream_chunk", handle_task_stream_chunk)
        
        # Execute single task from command line
        logger.debug(f"Solving task with agent: {task_content}")
        if config.max_iterations < 1:
            raise ValueError("max_iterations must be greater than 0")
        result = agent.solve_task(
            task=task_content, max_iterations=config.max_iterations, streaming=not config.no_stream
        )
        logger.debug(f"Task solved with result: {result} using {config.max_iterations} iterations")

        console.print(
            Panel.fit(
                f"[bold]Task Result:[/bold]\n{result}", title="[bold]Execution Output[/bold]", border_style="green"
            )
        )

    # INTERACTIVE MODE
    else:
        # Interactive mode
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
            f"Created agent for mode: {config.mode} with model: {config.model_name}, vision model: {config.vision_model_name}, no_stream: {config.no_stream}"
        )

        events = [
            "task_start",
            "task_think_start",
            "task_think_end",
            "task_complete",
            "tool_execution_start",
            "tool_execution_end",
            "error_max_iterations_reached",
            "memory_full",
            "memory_compacted",
            "memory_summary",
        ]

        # Stream handler for interactive mode
        def handle_interactive_stream_chunk(event: str, data: any) -> None:
            """Stream chunk handler for interactive mode - prints directly."""
            if current_spinner:
                stop_spinner(console)
            
            # Handle different data formats
            if data is None:
                return
            elif isinstance(data, str):
                # Direct string data
                console.print(data, end="", markup=False)
            elif isinstance(data, dict) and "data" in data:
                # Dictionary with 'data' key
                console.print(data["data"], end="", markup=False)
            elif isinstance(data, dict):
                # Dictionary without 'data' key, use the str representation
                logger.debug(f"Stream chunk data without 'data' key: {data}")
                console.print(str(data), end="", markup=False)
            else:
                # Fallback for any other type
                try:
                    console.print(str(data), end="", markup=False)
                except Exception as e:
                    logger.error(f"Error printing stream chunk: {e}")

        # Register event handlers for interactive mode
        agent.event_emitter.on(
            event=events,
            listener=console_print_events,
        )
        
        # Register interactive stream handler
        agent.event_emitter.on(
            event="stream_chunk",
            listener=handle_interactive_stream_chunk,
        )

        logger.debug("Registered event handlers for agent events with events: {events}")

        interactive_task_runner(agent, console, config.max_iterations, config.no_stream)