#!/usr/bin/env python
"""Main module for the QuantaLogic agent."""

# Standard library imports
import argparse
import sys
import warnings

# Suppress specific warnings related to Pydantic's V2 configuration changes
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="pydantic.*",
    message=".*config keys have changed in V2:.*|.*'fields' config key is removed in V2.*",
)

# Third-party imports
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.prompt import Confirm  # noqa: E402

# Local application imports
from quantalogic.agent_config import (  # noqa: E402
    MODEL_NAME,
    create_agent,
    create_coding_agent,  # noqa: F401
    create_orchestrator_agent,  # noqa: F401
)
from quantalogic.interactive_text_editor import get_multiline_input  # noqa: E402
from quantalogic.print_event import print_events  # noqa: E402

main_agent = create_agent(MODEL_NAME)

main_agent.event_emitter.on(
    [
        "task_complete",
        "task_think_start",
        "task_think_end",
        "tool_execution_start",
        "tool_execution_end",
        "error_max_iterations_reached",
        "memory_full",
        "memory_compacted",
        "memory_summary",
    ],
    print_events,
)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="QuantaLogic AI Assistant")
    parser.add_argument("--version", action="store_true", help="show version information")
    parser.add_argument("--execute-file", type=str, help="execute task from file")
    parser.add_argument("--verbose", action="store_true", help="enable verbose output")
    parser.add_argument(
        "--model",
        type=str,
        default=MODEL_NAME,
        help='specify the model to use (litellm format, e.g. "openrouter/deepseek-chat")',
    )
    return parser.parse_args()


def get_task_from_file(file_path):
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


def get_task_from_args(args):
    """Extract task from command line arguments."""
    task_args = []
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] in ["--version", "--execute-file", "--verbose", "--model"]:
            i += 2 if sys.argv[i] in ["--execute-file", "--model"] else 1
        else:
            task_args.append(sys.argv[i])
            i += 1
    # Return empty string if only --model is provided
    if not task_args and any(arg in sys.argv for arg in ["--model"]):
        return ""
    return " ".join(task_args)


def display_welcome_message(console, model_name):
    """Display the welcome message and instructions."""
    console.print(
        Panel.fit(
            "[bold cyan]🌟 Welcome to QuantaLogic AI Assistant! 🌟[/bold cyan]\n\n"
            "[green]🎯 How to Use:[/green]\n\n"
            "1. [bold]Describe your task[/bold]: Tell the AI what you need help with.\n"
            '   - Example: "Write a Python function to calculate Fibonacci numbers."\n'
            '   - Example: "Explain quantum computing in simple terms."\n'
            '   - Example: "Generate a list of 10 creative project ideas."\n'
            '   - Example: "Create a project plan for a new AI startup.\n'
            '   - Example: "Help me debug this Python code."\n\n'
            "2. [bold]Submit your task[/bold]: Press [bold]Enter[/bold] twice to send your request.\n\n"
            "3. [bold]Exit the app[/bold]: Leave the input blank and press [bold]Enter[/bold] twice to close the assistant.\n\n"
            f"[yellow]ℹ️ System Info:[/yellow]\n\n"
            f"- Version: {get_version()}\n"
            f"- Model: {model_name}\n\n"
            "[bold magenta]💡 Pro Tips:[/bold magenta]\n\n"
            "- Be as specific as possible in your task description to get the best results!\n"
            "- Use clear and concise language when describing your task\n"
            "- For coding tasks, include relevant context and requirements\n"
            "- The AI can handle complex tasks - don't hesitate to ask challenging questions!",
            title="[bold]Instructions[/bold]",
            border_style="blue",
        )
    )


def main():
    """Main entry point for the QuantaLogic AI Assistant."""
    console = Console()
    args = parse_arguments()

    if args.version:
        console.print(f"QuantaLogic version: {get_version()}")
        sys.exit(0)

    try:
        if args.execute_file:
            task = get_task_from_file(args.execute_file)
        else:
            task = get_task_from_args(args)
            if not task:  # If no task is provided in arguments, go to interactive mode
                display_welcome_message(console, args.model)
                task = get_multiline_input(console).strip()
                if not task:
                    console.print("[yellow]No task provided. Exiting...[/yellow]")
                    sys.exit(2)
    except Exception as e:
        console.print(f"[red]{str(e)}[/red]")
        sys.exit(1)

    # Bypass task preview and confirmation if --model is provided
    if not args.model == MODEL_NAME:
        console.print(
            Panel.fit(
                f"[bold]Task to be submitted:[/bold]\n{task}", title="[bold]Task Preview[/bold]", border_style="blue"
            )
        )
        if not Confirm.ask("[bold]Are you sure you want to submit this task?[/bold]"):
            console.print("[yellow]Task submission cancelled. Exiting...[/yellow]")
            sys.exit(0)

    # agent = create_agent(args.model)
    agent = create_coding_agent(args.model)
    # agent = create_orchestrator_agent(args.model)
    result = agent.solve_task(task=task, max_iterations=300)

    console.print(
        Panel.fit(f"[bold]Task Result:[/bold]\n{result}", title="[bold]Execution Output[/bold]", border_style="green")
    )


def get_version():
    """Get the current version of the package."""
    return "QuantaLogic version: 1.0.0"


if __name__ == "__main__":
    main()
