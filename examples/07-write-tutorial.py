#!/usr/bin/env -S uv run

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "quantalogic",
# ]
# ///

import os
from typing import Any

from rich.console import Console
from rich.prompt import Confirm, Prompt

from quantalogic import Agent
from quantalogic.console_print_events import console_print_events
from quantalogic.console_print_token import console_print_token
from quantalogic.tools import (
    InputQuestionTool,
    ListDirectoryTool,
    LLMTool,
    ReadFileBlockTool,
    ReadFileTool,
    ReplaceInFileTool,
    RipgrepTool,
    SearchDefinitionNamesTool,
    WriteFileTool,
)

MODEL_NAME = "openrouter/deepseek/deepseek-chat"

## You can use any model using the litellm format

# You must use model powerful enough to handle the task (at least gpt-4o-mini)

# MODEL_NAME = "openrouter/openai/gpt-4o-mini"
# MODEL_NAME = "openrouter/anthropic/claude-3.5-sonnet"
# MODEL_NAME = "anthropic/claude-3.5-sonnet"


# API key verification ensures service availability at startup
# Separate keys for different services enable flexible provider switching
# without requiring code modifications, supporting future scalability
if not os.environ.get("DEEPSEEK_API_KEY"):
    raise ValueError("DEEPSEEK_API_KEY environment variable is not set")


agent = Agent(
    model_name=MODEL_NAME,
    tools=[
        SearchDefinitionNamesTool(),
        RipgrepTool(),
        WriteFileTool(),
        ReadFileTool(),
        ReplaceInFileTool(),
        ReadFileBlockTool(),
        ListDirectoryTool(),
        InputQuestionTool(),
        LLMTool(
            model_name=MODEL_NAME, on_token=console_print_token
        ),  # LLMTool can be used to explore a specific latent space
    ],
)

spinner = None


def console_spinner_on(event: str, data: Any | None = None) -> None:
    """
    Start a console spinner to indicate ongoing processing.

    Args:
        event: A descriptive string indicating the event triggering the spinner
        data: Optional additional context data for the event
    """
    global spinner
    console = Console()
    spinner = console.status(f"Processing: {event}")
    spinner.start()


def console_spinner_off(event: str, data: Any | None = None) -> None:
    """
    Stop the active console spinner.

    Args:
        event: A descriptive string indicating the event completing the spinner
        data: Optional additional context data for the event
    """
    global spinner
    if spinner is not None:
        spinner.stop()


# Comprehensive event monitoring implemented through wildcard listener
# to support multiple critical functions:
# 1. Debugging through complete activity audit trail
# 2. Real-time progress visibility for better user experience
# 3. Foundation for future analytics capabilities
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

agent.event_emitter.on(event=["task_solve_start"], listener=console_spinner_on)
agent.event_emitter.on(event=["task_solve_end"], listener=console_spinner_off)

agent.event_emitter.on(event=["stream_chunk"], listener=console_print_token)
agent.event_emitter.on(event=["stream_chunk"], listener=console_spinner_off)


def interactive_task_prompt(
    default_topic: str = "Python",
    default_chapters: int = 3,
    default_level: str = "Beginner",
    default_words: int = 500,
    default_target_dir: str = "./tutorial",
) -> dict:
    """
    Interactively prompt the user for tutorial details using rich.

    Args:
        default_topic: Default tutorial topic
        default_chapters: Default number of chapters
        default_level: Default tutorial difficulty level
        default_words: Default target words per chapter
        default_target_dir: Default target directory for tutorial

    Returns:
        A dictionary with user-specified tutorial parameters
    """
    console = Console()

    console.print("[bold green]Interactive Tutorial Planner[/bold green]")
    console.print("Let's create an awesome tutorial together! 📘", style="italic")

    # Using rich library for enhanced user interaction with styled prompts
    # Validation implemented after initial input to maintain conversational flow
    # while ensuring data quality
    topic = Prompt.ask("What topic would you like to write about?", default=default_topic)

    chapters = Prompt.ask("How many chapters do you want?", default=str(default_chapters))

    # Post-input validation maintains user experience while ensuring data integrity
    # by allowing correction rather than preemptive constraints
    while not (chapters.isdigit() and int(chapters) > 0):
        console.print("[red]Please enter a valid number of chapters (greater than 0).[/red]")
        chapters = Prompt.ask("How many chapters do you want?", default=str(default_chapters))

    level = Prompt.ask(
        "What difficulty level?", default=default_level, choices=["Beginner", "Intermediate", "Advanced"]
    )

    words = Prompt.ask("Target words per chapter?", default=str(default_words))

    # Add validation after asking
    while not (words.isdigit() and int(words) > 0):
        console.print("[red]Please enter a valid number of words (greater than 0).[/red]")
        words = Prompt.ask("Target words per chapter?", default=str(default_words))

    target_dir = Prompt.ask("Target directory for the tutorial?", default=default_target_dir)

    # Confirm details
    console.print("\n[bold]Tutorial Details:[/bold]")
    console.print(f"Topic: [cyan]{topic}[/cyan]")
    console.print(f"Chapters: [cyan]{chapters}[/cyan]")
    console.print(f"Level: [cyan]{level}[/cyan]")
    console.print(f"Words per Chapter: [cyan]{words}[/cyan]")
    console.print(f"Target Directory: [cyan]{target_dir}[/cyan]")

    is_confirmed = Confirm.ask("Are these details correct?")

    if not is_confirmed:
        console.print("[yellow]Tutorial planning cancelled.[/yellow]")
        return {}

    return {"topic": topic, "chapters": int(chapters), "level": level, "words": int(words), "target_dir": target_dir}


def preparate_task(
    topic: str = "Python",
    chapters: int = 3,
    level: str = "Beginner",
    words: int = 500,
    target_dir: str = "./tutorial",
):
    # Get interactive details, falling back to default parameters
    task_details = interactive_task_prompt(
        default_topic=topic,
        default_chapters=chapters,
        default_level=level,
        default_words=words,
        default_target_dir=target_dir,
    )

    # If user cancels, return empty string or handle as needed
    if not task_details:
        return ""

    return f"""
# Task 

Write the best possible tutorial on a specific topic.

## Tutorial Specifications

- Topic: {task_details['topic']}
- Number of Chapters: {task_details['chapters']}
- Difficulty Level: {task_details['level']}
- Words per Chapter: {task_details['words']}
- Target Directory: {task_details['target_dir']}

## Step 1: Assess the user's needs and preferences

Please evaluate your understanding of the topic to determine if you can advance to step 2. 


If you feel unable to do so, kindly explain to the user the reasons for this.


## Step 2: Generate a tutorial based on the user's needs and preferences

- First generate a detailled outline of the tutorial
- Then generate the actual tutorial content based on the outline, one file by chapter. 

 Guide for writing a tutorial:

    - Use markdown to write the tutorial
    - Use Richard Feynman's style to explain difficult concepts, never mention Richard Feynman
    - Use code examples to illustrate concepts, use an example oriented approach
    - Include some mermaid diagrams to illustrate complex concepts if useful
    - You can use emojis to add fun to your tutorial
    - Be clear and concise, always start by WHY, then WHAT, then HOW

    """


task_description = preparate_task()

result = agent.solve_task(task_description, streaming=True)
print(result)
