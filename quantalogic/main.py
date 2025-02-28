#!/usr/bin/env python
"""Main module for the QuantaLogic agent."""

# Standard library imports
import sys
from typing import Optional

# Third-party imports
import click
from dotenv import load_dotenv
from fuzzywuzzy import process
from loguru import logger

from quantalogic.version import get_version

# Load environment variables from .env file
load_dotenv()


# Configure logger
logger.remove()

from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402

# Local application imports
from quantalogic.agent_config import (  # noqa: E402
    MODEL_NAME,
)
from quantalogic.config import QLConfig  # noqa: E402
from quantalogic.task_runner import task_runner  # noqa: E402
from quantalogic.utils.get_all_models import get_all_models  # noqa: E402

# Platform-specific imports
try:
    if sys.platform == "win32":
        import msvcrt  # Built-in Windows module
    else:
        import termios
        import tty
except ImportError as e:
    logger.warning(f"Could not import platform-specific module: {e}")
    # Fall back to basic terminal handling if imports fail
    msvcrt = None
    termios = None
    tty = None

AGENT_MODES = ["code", "basic", "interpreter", "full", "code-basic", "search", "search-full"]


def setup_terminal():
    """Configure terminal settings based on platform."""
    if sys.platform == "win32":
        if msvcrt:
            return None  # Windows terminal is already configured
        logger.warning("msvcrt module not available on Windows")
        return None
    else:
        if termios and tty:
            try:
                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                tty.setraw(fd)
                return old_settings
            except (termios.error, AttributeError) as e:
                logger.warning(f"Failed to configure terminal: {e}")
                return None
        return None


def restore_terminal(old_settings):
    """Restore terminal settings based on platform."""
    if sys.platform != "win32" and termios and old_settings:
        try:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
        except (termios.error, AttributeError) as e:
            logger.warning(f"Failed to restore terminal settings: {e}")


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
    help="Specify the model to use (litellm format). Examples:\n"
    "  - openai/gpt-4o-mini\n"
    "  - openai/gpt-4o\n"
    "  - anthropic/claude-3.5-sonnet\n"
    "  - deepseek/deepseek-chat\n"
    "  - deepseek/deepseek-reasoner\n"
    "  - openrouter/deepseek/deepseek-r1\n"
    "  - openrouter/openai/gpt-4o",
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
@click.option(
    "--thinking-model",
    type=str,
    default="default",
    help="The thinking model to use",
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
    thinking_model: str,
) -> None:
    """QuantaLogic AI Assistant - A powerful AI tool for various tasks.

    Environment Variables:
      - OpenAI: Set `OPENAI_API_KEY` to your OpenAI API key.
      - Anthropic: Set `ANTHROPIC_API_KEY` to your Anthropic API key.
      - DeepSeek: Set `DEEPSEEK_API_KEY` to your DeepSeek API key.
    Use a `.env` file or export these variables in your shell for seamless integration.
    """
    if version:
        console = Console()
        current_version = get_version()
        console.print(
            Panel(f"QuantaLogic Version: [bold green]{current_version}[/bold green]", title="Version Information")
        )
        ctx.exit()

    if ctx.invoked_subcommand is None:
        config = QLConfig(
            model_name=model_name,
            verbose=verbose,
            mode=mode,
            log=log,
            vision_model_name=vision_model_name,
            max_iterations=max_iterations,
            compact_every_n_iteration=compact_every_n_iteration,
            max_tokens_working_memory=max_tokens_working_memory,
            no_stream=False,  # Default value for backward compatibility
            thinking_model_name=thinking_model,
        )
        ctx.invoke(
            task,
            model_name=config.model_name,
            verbose=config.verbose,
            mode=config.mode,
            log=config.log,
            vision_model_name=config.vision_model_name,
            max_iterations=config.max_iterations,
            compact_every_n_iteration=config.compact_every_n_iteration,
            max_tokens_working_memory=config.max_tokens_working_memory,
            thinking_model=thinking_model,
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
@click.option(
    "--thinking-model",
    type=str,
    default="default",
    help="The thinking model to use",
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
    thinking_model: str,
) -> None:
    console = Console()

    try:
        config = QLConfig(
            model_name=model_name,
            verbose=verbose,
            mode=mode,
            log=log,
            vision_model_name=vision_model_name,
            max_iterations=max_iterations,
            compact_every_n_iteration=compact_every_n_iteration,
            max_tokens_working_memory=max_tokens_working_memory,
            no_stream=no_stream,
            thinking_model_name=thinking_model,
        )

        task_runner(
            console,
            file,
            config,
            task,
        )
    except Exception as e:
        console.print(f"[red]{str(e)}[/red]")
        logger.error(f"Error in task execution: {e}", exc_info=True)
        sys.exit(1)


@cli.command()
@click.option("--search", type=str, help="Fuzzy search for models containing the given string.")
def list_models(search: Optional[str] = None):
    """List supported LiteLLM models with optional fuzzy search.

    If a search term is provided, it will return models that closely match the term.
    """
    console = Console()
    all_models = get_all_models()

    if search:
        # Perform fuzzy matching
        matched_models = process.extractBests(search, all_models, limit=None, score_cutoff=70)
        models = [model for model, score in matched_models]
    else:
        models = all_models

    console.print(Panel(f"Total Models: {len(models)} " f"({len(all_models)} total)", title="Supported LiteLLM Models"))

    if not models:
        console.print(f"[yellow]No models found matching '[bold]{search}[/bold]'[/yellow]")
        return

    for model in sorted(models):
        console.print(f"- {model}")


def main():
    """Main entry point."""
    old_settings = setup_terminal()
    try:
        cli()  # type: ignore
    finally:
        restore_terminal(old_settings)


if __name__ == "__main__":
    main()
