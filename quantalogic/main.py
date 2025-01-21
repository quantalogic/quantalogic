#!/usr/bin/env python
"""Main module for the QuantaLogic agent."""

# Standard library imports
import sys
from typing import Optional

# Third-party imports
import click
from loguru import logger

from quantalogic.version import get_version

# Configure logger
logger.remove()

from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402

# Local application imports
from quantalogic.agent_config import (  # noqa: E402
    MODEL_NAME,
)
from quantalogic.task_runner import task_runner  # noqa: E402

AGENT_MODES = ["code", "basic", "interpreter", "full", "code-basic", "search", "search-full"]


@click.group(invoke_without_command=True)
@click.option(
    "--compact-every-n-iteration",
    type=int,
    default=None,
    help="Set the frequency of memory compaction for the agent (default: max_iterations).",
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
    help="Set the maximum number of tokens allowed in the working memory.",
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
        current_version = get_version()
        console.print(
            Panel(f"QuantaLogic Version: [bold green]{current_version}[/bold green]", title="Version Information")
        )
        ctx.exit()

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
@click.option("--file", type=str, help="Path to task file or URL.")
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
    help="Set the frequency of memory compaction for the agent (default: max_iterations).",
)
@click.option(
    "--max-tokens-working-memory",
    type=int,
    default=None,
    help="Set the maximum number of tokens allowed in the working memory.",
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
    console = Console()

    try:
        task_runner(
            console,
            file,
            model_name,
            verbose,
            mode,
            log,
            vision_model_name,
            task,
            max_iterations,
            compact_every_n_iteration,
            max_tokens_working_memory,
            no_stream,
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
