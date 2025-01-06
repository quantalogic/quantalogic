#!/usr/bin/env python
"""Main module for the QuantaLogic agent."""

# Standard library imports
import sys
from typing import Optional

# Third-party imports
import click
from loguru import logger

# Configure logger
logger.remove()  # Remove default logger

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
    create_orchestrator_agent,
)
from quantalogic.interactive_text_editor import get_multiline_input  # noqa: E402
from quantalogic.print_event import console_print_events  # noqa: E402
from quantalogic.version import get_version  # noqa: E402

AGENT_MODES = ["code", "basic", "interpreter", "full", "code-basic"]


def create_agent_for_mode(mode: str, model_name: str) -> Agent:
    """Create an agent based on the specified mode."""
    logger.debug(f"Creating agent for mode: {mode} with model: {model_name}")
    if mode == "code":
        logger.debug("Creating code agent without basic mode")
        return create_coding_agent(model_name, basic=False)
    if mode == "code-basic":
        return create_coding_agent(model_name, basic=True)
    elif mode == "basic":
        return create_orchestrator_agent(model_name)
    elif mode == "full":
        return create_full_agent(model_name)
    elif mode == "interpreter":
        return create_interpreter_agent(model_name)
    else:
        raise ValueError(f"Unknown agent mode: {mode}")


def configure_logger(log_level: str) -> None:
    """Configure the logger with the specified log level and format."""
    logger.remove()
    logger.add(sys.stderr, level=log_level.upper(), format="{time} | {level} | {message}")
    logger.info(f"Log level set to: {log_level}")


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


def display_welcome_message(console: Console, model_name: str) -> None:
    """Display the welcome message and instructions."""
    version = get_version()
    console.print(
        Panel.fit(
            f"[bold cyan]🌟 Welcome to QuantaLogic AI Assistant v{version} ! 🌟[/bold cyan]\n\n"
            "[green]🎯 How to Use:[/green]\n\n"
            "1. [bold]Describe your task[/bold]: Tell the AI what you need help with.\n"
            "2. [bold]Submit your task[/bold]: Press [bold]Enter[/bold] twice to send your request.\n\n"
            "3. [bold]Exit the app[/bold]: Leave the input blank and press [bold]Enter[/bold] twice to close the assistant.\n\n"
            f"[yellow]ℹ️ System Info:[/yellow]\n\n"
            f"- Version: {get_version()}\n"
            f"- Model: {model_name}\n\n"
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
@click.option("--version", is_flag=True, help="Show version information.")
@click.option(
    "--model-name",
    default=MODEL_NAME,
    help='Specify the model to use (litellm format, e.g. "openrouter/deepseek-chat").',
)
@click.option("--log", type=click.Choice(["info", "debug", "warning"]), default="info", help="Set logging level (info/debug/warning).")
@click.option("--verbose", is_flag=True, help="Enable verbose output.")
@click.option("--mode", type=click.Choice(AGENT_MODES), default="code", help="Agent mode (code/search/full).")
@click.pass_context
def cli(ctx: click.Context, version: bool, model_name: str, verbose: bool, mode: str, log: str) -> None:
    """QuantaLogic AI Assistant - A powerful AI tool for various tasks."""
    if version:
        console = Console()
        console.print(f"QuantaLogic version: {get_version()}")
        sys.exit(0)
    if ctx.invoked_subcommand is None:
        ctx.invoke(task, model_name=model_name, verbose=verbose, mode=mode, log=log)


@cli.command()
@click.option("--file", type=click.Path(exists=True), help="Path to task file.")
@click.option(
    "--model-name",
    default=MODEL_NAME,
    help='Specify the model to use (litellm format, e.g. "openrouter/deepseek-chat").',
)
@click.option("--verbose", is_flag=True, help="Enable verbose output.")
@click.option("--mode", type=click.Choice(AGENT_MODES), default="code", help="Agent mode (code/search/full).")
@click.argument("task", required=False)
def task(file: Optional[str], model_name: str, verbose: bool, mode: str, task: Optional[str], log: str) -> None:
    """Execute a task with the QuantaLogic AI Assistant."""
    console = Console()
    switch_verbose(verbose, log)

    try:
        if file:
            task_content = get_task_from_file(file)
        else:
            if task:
                task_content = task
            else:
                display_welcome_message(console, model_name)
                logger.info("Waiting for user input...")
                task_content = get_multiline_input(console).strip()
                logger.info(f"User input received. Task content: {task_content}")
                if not task_content:
                    logger.info("No task provided. Exiting...")
                    console.print("[yellow]No task provided. Exiting...[/yellow]")
                    sys.exit(2)

        if model_name != MODEL_NAME:
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

        logger.debug(f"Creating agent for mode: {mode} with model: {model_name}")
        agent = create_agent_for_mode(mode, model_name)
        logger.debug(f"Created agent for mode: {mode} with model: {model_name}")

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
        agent.event_emitter.on(
            event=events,
            listener=console_print_events,
        )
        logger.debug("Registered event handlers for agent events with events: {events}")

        logger.debug(f"Solving task with agent: {task_content}")
        result = agent.solve_task(task=task_content, max_iterations=300)
        logger.debug(f"Task solved with result: {result}")

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
    """Entry point for the quantalogic CLI."""
    cli()


if __name__ == "__main__":
    main()
