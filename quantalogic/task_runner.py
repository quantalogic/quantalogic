"""Task runner module for executing tasks with the QuantaLogic AI Assistant."""

import sys
from threading import Lock
from typing import Optional

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

# Spinner control
spinner_lock = Lock()
current_spinner = None


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

    set_litellm_verbose(verbose_mode)


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
    """Run tasks interactively, asking the user if they want to continue after each task.

    Args:
        agent: The agent instance to use for solving tasks
        console: Rich console instance for output
        max_iterations: Maximum number of iterations per task
        no_stream: Disable streaming output
    """
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
    """Execute a task with the QuantaLogic AI Assistant.

    Args:
        console: Rich console instance for output
        file: Optional path to task file
        config: QuantaLogic configuration object
        task: Optional task string
    """
    switch_verbose(config.verbose, config.log)

    # Create the agent instance with the specified configuration
    agent = create_agent_for_mode(
        mode=config.mode,
        model_name=config.model_name,
        vision_model_name=config.vision_model_name,
        thinking_model_name=config.thinking_model_name,
        compact_every_n_iteration=config.compact_every_n_iteration,
        max_tokens_working_memory=config.max_tokens_working_memory,
    )

    AgentRegistry.register_agent("main_agent", agent)

    if file:
        task_content = get_task_from_file(file)
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
    else:
        if task:
            check_new_version()
            task_content = task
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

            # def ask_continue(event: str, data: any) -> None:
            #    ## Ask for ctrl+return
            #    if event == "task_think_end":
            #        ## Wait return on the keyboard
            #        input("Press [Enter] to continue...")

            # Add spinner control to event handlers
            def handle_task_think_start(*args, **kwargs):
                start_spinner(console)

            def handle_task_think_end(*args, **kwargs):
                stop_spinner(console)

            def handle_stream_chunk(event: str, data: str) -> None:
                if current_spinner:
                    stop_spinner(console)
                if data is not None:
                    console.print(data, end="", markup=False)

            # agent.event_emitter.on(
            #    event="task_think_end",
            #    listener=ask_continue,
            # )

            agent.event_emitter.on(
                event=events,
                listener=console_print_events,
            )

            agent.event_emitter.on(
                event="task_think_start",
                listener=handle_task_think_start,
            )

            agent.event_emitter.on(
                event="task_think_end",
                listener=handle_task_think_end,
            )

            agent.event_emitter.on(
                event="stream_chunk",
                listener=handle_stream_chunk,
            )

            logger.debug("Registered event handlers for agent events with events: {events}")

            interactive_task_runner(agent, console, config.max_iterations, config.no_stream)
