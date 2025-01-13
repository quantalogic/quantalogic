#!/usr/bin/env python
"""Main module for the QuantaLogic agent."""

# Standard library imports
import random
import sys
from typing import Optional

# Third-party imports
import click
from loguru import logger

from quantalogic.console_print_events import console_print_events
from quantalogic.utils.check_version import check_if_is_latest_version
from quantalogic.version import get_version

# Configure logger
logger.remove()  # Remove default logger

from threading import Lock  # noqa: E402

from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.prompt import Confirm  # noqa: E402

from quantalogic.agent import Agent  # noqa: E402

# Local application imports
from quantalogic.agent_config import (  # noqa: E402
    MODEL_NAME,
    create_coding_agent,
    create_full_agent,
    create_interpreter_agent,
    create_basic_agent,
)
from quantalogic.interactive_text_editor import get_multiline_input  # noqa: E402
from quantalogic.search_agent import create_search_agent  # noqa: E402

AGENT_MODES = ["code", "basic", "interpreter", "full", "code-basic", "search", "search-full"]


def create_agent_for_mode(mode: str, model_name: str, vision_model_name: str | None, no_stream: bool = False, compact_every_n_iteration: int | None = None, max_tokens_working_memory: int | None = None) -> Agent:
    """Create an agent based on the specified mode."""
    logger.debug(f"Creating agent for mode: {mode} with model: {model_name}")
    logger.debug(f"Using vision model: {vision_model_name}")
    logger.debug(f"Using no_stream: {no_stream}")
    logger.debug(f"Using compact_every_n_iteration: {compact_every_n_iteration}")
    logger.debug(f"Using max_tokens_working_memory: {max_tokens_working_memory}")
    if mode == "code":
        logger.debug("Creating code agent without basic mode")
        return create_coding_agent(model_name, vision_model_name, basic=False, no_stream=no_stream, compact_every_n_iteration=compact_every_n_iteration, max_tokens_working_memory=max_tokens_working_memory)
    if mode == "code-basic":
        return create_coding_agent(model_name, vision_model_name, basic=True, no_stream=no_stream, compact_every_n_iteration=compact_every_n_iteration, max_tokens_working_memory=max_tokens_working_memory)
    elif mode == "basic":
        return create_basic_agent(model_name, vision_model_name, no_stream=no_stream, compact_every_n_iteration=compact_every_n_iteration, max_tokens_working_memory=max_tokens_working_memory)
    elif mode == "full":
        return create_full_agent(model_name, vision_model_name, no_stream=no_stream, compact_every_n_iteration=compact_every_n_iteration, max_tokens_working_memory=max_tokens_working_memory)
    elif mode == "interpreter":
        return create_interpreter_agent(model_name, vision_model_name, no_stream=no_stream, compact_every_n_iteration=compact_every_n_iteration, max_tokens_working_memory=max_tokens_working_memory)
    elif mode == "search":
        return create_search_agent(model_name, no_stream=no_stream, compact_every_n_iteration=compact_every_n_iteration, max_tokens_working_memory=max_tokens_working_memory)
    if mode == "search-full":
        return create_search_agent(model_name, mode_full=True, no_stream=no_stream, compact_every_n_iteration=compact_every_n_iteration, max_tokens_working_memory=max_tokens_working_memory)
    else:
        raise ValueError(f"Unknown agent mode: {mode}")


def check_new_version():
    # Randomly check for updates (1 in 10 chance)
    if random.randint(1, 10) == 1:
        try:
            current_version = get_version()
            has_new_version, latest_version = check_if_is_latest_version()

            if has_new_version:
                console = Console()
                console.print(
                    Panel.fit(
                        f"[yellow]⚠️  Update Available![/yellow]\n\n"
                        f"Current version: [bold]{current_version}[/bold]\n"
                        f"Latest version: [bold]{latest_version}[/bold]\n\n"
                        "To update, run:\n"
                        "[bold]pip install --upgrade quantalogic[/bold]\n"
                        "or if using pipx:\n"
                        "[bold]pipx upgrade quantalogic[/bold]",
                        title="[bold]Update Available[/bold]",
                        border_style="yellow",
                    )
                )
        except Exception:
            return


def configure_logger(log_level: str) -> None:
    """Configure the logger with the specified log level and format."""
    logger.remove()
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


def get_task_from_file(file_path: str) -> str:
    """Get task content from specified file."""
    try:
        with open(file_path, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"Error: File '{file_path}' not found.")
    except PermissionError:
        raise PermissionError(f"Error: Permission denied when reading '{file_path}'.")
    except Exception as e:
        raise Exception(f"Unexpected error reading file: {e}")


# Spinner control
spinner_lock = Lock()
current_spinner = None

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


def display_welcome_message(
    console: Console, 
    model_name: str, 
    vision_model_name: str | None, 
    max_iterations: int = 50, 
    compact_every_n_iteration: int | None = None,
    max_tokens_working_memory: int | None = None,
    mode: str = "basic"
) -> None:
    """Display the welcome message and instructions."""
    version = get_version()
    console.print(
        Panel.fit(
            f"[bold cyan]🌟 Welcome to QuantaLogic AI Assistant v{version} ! 🌟[/bold cyan]\n\n"
            "[green]🎯 How to Use:[/green]\n\n"
            "1. [bold]Describe your task[/bold]: Tell the AI what you need help with.\n"
            "2. [bold]Submit your task[/bold]: Press [bold]Enter[/bold] twice to send your request.\n\n"
            "3. [bold]Exit the app[/bold]: Leave the input blank and press [bold]Enter[/bold] twice to close the assistant.\n\n"
            f"[yellow] 🤖 System Info:[/yellow]\n\n"
            "\n"
            f"- Model: {model_name}\n"
            f"- Vision Model: {vision_model_name}\n"
            f"- Mode: {mode}\n"
            f"- Max Iterations: {max_iterations}\n"
            f"- Memory Compact Frequency: {compact_every_n_iteration or 'Default (Max Iterations)'}\n"
            f"- Max Working Memory Tokens: {max_tokens_working_memory or 'Default'}\n\n"
            "[bold magenta]💡 Pro Tips:[/bold magenta]\n\n"
            "- Be as specific as possible in your task description to get the best results!\n"
            "- Use clear and concise language when describing your task\n"
            "- For coding tasks, include relevant context and requirements\n"
            "- The coding agent mode can handle complex tasks - don't hesitate to ask challenging questions!",
            title="[bold]Instructions[/bold]",
            border_style="blue",
        )
    )


@click.group(invoke_without_command=True)
@click.option(
    "--compact-every-n-iteration",
    type=int,
    default=None,
    help="Set the frequency of memory compaction for the agent (default: max_iterations)."
)
@click.option("--version", is_flag=True, help="Show version information.")
@click.option(
    "--model-name",
    default=MODEL_NAME,
    help='Specify the model to use (litellm format, e.g. "openrouter/deepseek/deepseek-chat").',
)
@click.option(
    "--log",
    type=click.Choice(["info", "debug", "warning"]),
    default="info",
    help="Set logging level (info/debug/warning).",
)
@click.option("--verbose", is_flag=True, help="Enable verbose output.")
@click.option("--mode", type=click.Choice(AGENT_MODES), default="basic", help="Agent mode (code/search/full).")
@click.option(
    "--vision-model-name",
    default=None,
    help='Specify the vision model to use (litellm format, e.g. "openrouter/A/gpt-4o-mini").',
)
@click.option(
    "--max-iterations",
    type=int,
    default=30,
    help="Maximum number of iterations for task solving (default: 30).",
)
@click.option(
    "--max-tokens-working-memory",
    type=int,
    default=None,
    help="Set the maximum number of tokens allowed in the working memory."
)
@click.pass_context
def cli(
    ctx: click.Context,
    version: bool,
    model_name: str,
    verbose: bool,
    mode: str,
    log: str,
    vision_model_name: str | None,
    max_iterations: int,
    compact_every_n_iteration: int | None,
    max_tokens_working_memory: int | None,
) -> None:
    """QuantaLogic AI Assistant - A powerful AI tool for various tasks."""
    if version:
        console = Console()
        console.print(f"QuantaLogic version: {get_version()}")
        sys.exit(0)
    if ctx.invoked_subcommand is None:
        ctx.invoke(
            task,
            model_name=model_name,
            verbose=verbose,
            mode=mode,
            log=log,
            vision_model_name=vision_model_name,
            max_iterations=max_iterations,
            compact_every_n_iteration=compact_every_n_iteration,
            max_tokens_working_memory=max_tokens_working_memory,
        )


@cli.command()
@click.option("--file", type=click.Path(exists=True), help="Path to task file.")
@click.option(
    "--model-name",
    default=MODEL_NAME,
    help='Specify the model to use (litellm format, e.g. "openrouter/deepseek/deepseek-chat").',
)
@click.option("--verbose", is_flag=True, help="Enable verbose output.")
@click.option("--mode", type=click.Choice(AGENT_MODES), default="basic", help="Agent mode (code/search/full).")
@click.option(
    "--log",
    type=click.Choice(["info", "debug", "warning"]),
    default="info",
    help="Set logging level (info/debug/warning).",
)
@click.option(
    "--vision-model-name",
    default=None,
    help='Specify the vision model to use (litellm format, e.g. "openrouter/openai/gpt-4o-mini").',
)
@click.option(
    "--max-iterations",
    type=int,
    default=30,
    help="Maximum number of iterations for task solving (default: 30).",
)
@click.option(
    "--compact-every-n-iteration",
    type=int,
    default=None,
    help="Set the frequency of memory compaction for the agent (default: max_iterations)."
)
@click.option(
    "--max-tokens-working-memory",
    type=int,
    default=None,
    help="Set the maximum number of tokens allowed in the working memory."
)
@click.option(
    "--no-stream",
    is_flag=True,
    help="Disable streaming output (default: streaming enabled).",
)
@click.argument("task", required=False)
def task(
    file: Optional[str],
    model_name: str,
    verbose: bool,
    mode: str,
    log: str,
    vision_model_name: str | None,
    task: Optional[str],
    max_iterations: int,
    compact_every_n_iteration: int | None,
    max_tokens_working_memory: int | None,
    no_stream: bool,
) -> None:
    """Execute a task with the QuantaLogic AI Assistant."""
    console = Console()
    switch_verbose(verbose, log)

    try:
        if file:
            task_content = get_task_from_file(file)
        else:
            if task:
                check_new_version()
                task_content = task
            else:
                display_welcome_message(
                    console, 
                    model_name, 
                    vision_model_name, 
                    max_iterations=max_iterations, 
                    compact_every_n_iteration=compact_every_n_iteration,
                    max_tokens_working_memory=max_tokens_working_memory,
                    mode=mode
                )
                check_new_version()
                logger.debug("Waiting for user input...")
                task_content = get_multiline_input(console).strip()
                logger.debug(f"User input received. Task content: {task_content}")
                if not task_content:
                    logger.info("No task provided. Exiting...")
                    console.print("[yellow]No task provided. Exiting...[/yellow]")
                    sys.exit(2)

        console.print(
            Panel.fit(
                f"[bold]Task to be submitted:[/bold]\n{task_content}",
                title="[bold]Task Preview[/bold]",
                border_style="blue",
            )
        )
        if not Confirm.ask("[bold]Are you sure you want to submit this task?[/bold]"):
            console.print("[yellow]Task submission cancelled. Exiting...[/yellow]")
            sys.exit(0)

        console.print(
            Panel.fit(
                "[green]✓ Task successfully submitted! Processing...[/green]",
                title="[bold]Status[/bold]",
                border_style="green",
            )
        )

        logger.debug(
            f"Creating agent for mode: {mode} with model: {model_name}, vision model: {vision_model_name}, no_stream: {no_stream}"
        )
        agent = create_agent_for_mode(mode, model_name, vision_model_name=vision_model_name, no_stream=no_stream, compact_every_n_iteration=compact_every_n_iteration, max_tokens_working_memory=max_tokens_working_memory)
        logger.debug(
            f"Created agent for mode: {mode} with model: {model_name}, vision model: {vision_model_name}, no_stream: {no_stream}"
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

        logger.debug(f"Solving task with agent: {task_content}")
        if max_iterations < 1:
            raise ValueError("max_iterations must be greater than 0")
        result = agent.solve_task(task=task_content, max_iterations=max_iterations, streaming=not no_stream)
        logger.debug(f"Task solved with result: {result} using {max_iterations} iterations")

        console.print(
            Panel.fit(
                f"[bold]Task Result:[/bold]\n{result}", title="[bold]Execution Output[/bold]", border_style="green"
            )
        )

    except Exception as e:
        console.print(f"[red]{str(e)}[/red]")
        logger.error(f"Error in task execution: {e}", exc_info=True)
        sys.exit(1)


def main():
    """Main Entry point"""
    cli()


if __name__ == "__main__":
    main()
