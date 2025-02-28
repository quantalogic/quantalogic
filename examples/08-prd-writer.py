#!/usr/bin/env -S uv run

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "quantalogic",
# ]
# ///

import os
import sys
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.spinner import Spinner
from rich.text import Text

from quantalogic import Agent
from quantalogic.console_print_events import console_print_events
from quantalogic.console_print_token import console_print_token
from quantalogic.tools import (
    JinjaTool,
    ListDirectoryTool,
    LLMTool,
    ReadFileBlockTool,
    ReadFileTool,
    ReplaceInFileTool,
    WriteFileTool,
)

MODEL_NAME = "deepseek/deepseek-chat"

# Ensuring API keys are configured
if not os.environ.get("DEEPSEEK_API_KEY"):
    raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

console = Console()


agent = Agent(
    model_name=MODEL_NAME,
    tools=[
        WriteFileTool(),
        ReadFileTool(),
        ReplaceInFileTool(),
        ReadFileBlockTool(),
        ListDirectoryTool(),
        JinjaTool(),
        LLMTool(model_name=MODEL_NAME, on_token=console_print_token),
    ],
)


# Spinner Manager with external control
class SpinnerManager:
    def __init__(self, console: Console, message: str = "Processing..."):
        self.console = console
        self.spinner = Spinner("dots", text=message, style="cyan")
        self.live = Live(self.spinner, refresh_per_second=10, console=self.console, transient=True)

    def start(self):
        self.live.start()

    def stop(self):
        self.live.stop()


# Initialize SpinnerManager
spinner_manager = SpinnerManager(console, "Generating PRD...")
spinner_manager.spinner_active = False

# Hooking into events
agent.event_emitter.on(
    [
        "task_complete",
        "task_think_start",
        "task_think_end",
        "tool_execution_start",
        "tool_execution_end",
        "error_max_iterations_reached",
    ],
    console_print_events,
)


def on_task_solve_start(event: str, data: Any | None = None) -> None:
    """Start the spinner when task solving begins."""
    spinner_manager.start()
    spinner_manager.spinner_active = True


def on_task_solve_end(event: str, data: Any | None = None) -> None:
    """Stop the spinner when task solving ends."""
    if spinner_manager.spinner_active:
        spinner_manager.stop()
        spinner_manager.spinner_active = False


def on_stream_chunk(event: str, data: Any | None = None) -> None:
    """Handle stream_chunk events by stopping the spinner and printing the token."""
    if spinner_manager.spinner_active:
        spinner_manager.stop()
        spinner_manager.spinner_active = False
    console_print_token(event, data)  # Print the token chunk


agent.event_emitter.on(event=["task_solve_start"], listener=on_task_solve_start)
agent.event_emitter.on(event=["task_solve_end"], listener=on_task_solve_end)
agent.event_emitter.on(event=["stream_chunk"], listener=on_stream_chunk)


def get_multiline_input(
    console: Console, prompt: str = "Paste your text below (Press Ctrl+D or type 'END' on a new line to finish):\n"
) -> str:
    """
    Capture and process multi-line input from the user, including pasted text.

    Args:
        console: Rich Console instance for displaying prompts
        prompt: Initial prompt message

    Returns:
        A single string containing all user input
    """
    console.print(panel_prompt(prompt))
    lines = []
    try:
        while True:
            line = Prompt.ask("", default="", show_default=False, console=console)
            if line.strip().upper() == "END":
                break
            lines.append(line)
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Input cancelled.[/yellow]")
        return ""
    return "\n".join(lines)


def panel_prompt(message: str) -> Panel:
    """
    Create a styled panel for prompts.

    Args:
        message: The message to display in the panel.

    Returns:
        A Rich Panel object.
    """
    return Panel(Text(message, style="italic"), style="dim", expand=False)


def review_input(console: Console, requirements: str) -> str:
    """
    Allow users to review their input.

    Args:
        console: Rich Console instance
        requirements: Text input to review

    Returns:
        Reviewed input text
    """
    markdown = Markdown(requirements)
    console.print("\n[bold]Your current input is as follows:[/bold]")
    console.print(markdown, style="cyan")
    return requirements


def interactive_prd_prompt(default_project: str = "New Product", default_target_dir: str = "./docs/prd") -> dict:
    """
    Interactive user prompts for collecting PRD-related information.

    Args:
        default_project: Default project name
        default_target_dir: Default output directory

    Returns:
        A dictionary containing all input details for the PRD
    """
    console.print(
        Panel(
            Text(
                "[bold green]PRD Writer Assistant[/bold green]\nLet's create your PRD! Please follow the prompts below. 📝",
                justify="center",
            ),
            style="bright_blue",
        )
    )

    project = Prompt.ask("Enter the name of your project", default=default_project, console=console)

    console.print("\n[bold]Project Requirements[/bold]")
    requirements = get_multiline_input(console)
    if not requirements:
        return {}
    requirements = review_input(console, requirements)

    target_dir = Prompt.ask("Where should the PRD be saved?", default=default_target_dir, console=console)

    summary = (
        "\n[bold]Summary of your PRD Details:[/bold]\n"
        f"• Project Name: [cyan]{project}[/cyan]\n"
        f"• Requirements:\n[cyan]{requirements}[/cyan]\n"
        f"• Target Directory: [cyan]{target_dir}[/cyan]"
    )
    console.print(summary)

    if not Confirm.ask("Are these details correct?", default=True, console=console):
        console.print("[yellow]PRD creation cancelled. Restart and try again![/yellow]")
        return {}

    return {"project": project, "requirements": requirements, "target_dir": target_dir}


def prepare_prd_task(project: str = "New Product", target_dir: str = "./docs/prd") -> str:
    """
    Prepares a Product Requirements Document (PRD) writing task based on user input.

    Args:
        project: The default project name.
        target_dir: The default output directory for PRD files.

    Returns:
        A detailed task description for creating the PRD.
    """
    details = interactive_prd_prompt(default_project=project, default_target_dir=target_dir)

    if not details:
        return ""

    task_description = f"""
# Task: Create a Product Requirements Document (PRD)

You are a 10x Product Manager responsible for developing a Product Requirements Document (PRD) for the following project:

**Project Name:** {details['project']}  
**Output Directory:** {details['target_dir']} (Format: Markdown)

## Workflow Steps:

### Step 1: Analyze Requirements
- Analyze these requirements: {details['requirements']} along with the last generated PRD.
- Conduct in-depth market research to identify the target users and their needs.
- Save findings in a separate file: `{details['target_dir']}/market_research.md`.

### Step 2: Feature Categorization
- Brainstorm a set of potential features and categorize them into **Core** and **Optional** using MoSCoW prioritization.
- Draw inspiration from the following books:
    - *Hooked: How to Build Habit-Forming Products* by Nir Eyal
    - *Inspired: How to Create Tech Products Customers Love* by Marty Cagan
- Document your findings in: `{details['target_dir']}/features.md`.

### Step 3: Develop PRD Sections
- Create individual files for each PRD section in the target directory: `{details['target_dir']}`:
    - Overview
    - Problem Statement
    - Target Users
    - Features (MVP & Future)
    - Success Metrics
    - Timeline

### Step 4: Review PRD Sections
- Review and critique the content of each section developed in Step 3, updating if necessary.
- Update each section as needed.

### Step 5: Draft the Final PRD
- Compile a cohesive first draft of the PRD encompassing all sections.
- Ensure the document is clear, readable, and navigable.
- Save as: `{details['target_dir']}/final_prd_draft.md`.

### Step 6: Draft Review
- Review the draft of the final PRD, providing constructive feedback and updates as needed.
- Write the feedback into a separate file: `{details['target_dir']}/final_feedback.md`.

### Step 7: Final PRD Creation
- Update the final PRD based on the feedback provided in Step 6.
- Produce the final updated PRD in a separate file: `{details['target_dir']}/final_prd.md`.

## Instructions:
Take inspiration from the following books to enrich your PRD:
- *Hooked: How to Build Habit-Forming Products* by Nir Eyal
- *Inspired: How to Create Tech Products Customers Love* by Marty Cagan
- *Escaping the Build Trap* by Melissa Perri
- *Good Strategy Bad Strategy* by Richard Rumelt
- *Crossing the Chasm* by Geoffrey A. Moore

## Goals:
- Generate a thorough PRD of at least 5000 words.
- Repeat the improvement process a minimum of 8 times for a solid final product.
- Ensure the product delivers an exceptional user experience and is financially viable.

"""

    return task_description


def main():
    task_description = prepare_prd_task()
    if task_description:
        try:
            agent.solve_task(task_description, streaming=True, max_iterations=50)
        except Exception as e:
            console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")
            sys.exit(1)
    else:
        console.print("[yellow]No task was prepared. Exiting.[/yellow]")


if __name__ == "__main__":
    main()
