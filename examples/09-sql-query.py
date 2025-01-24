#!/usr/bin/env -S uv run

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "streamlit",
#     "yfinance",
#     "pandas",
#     "plotly",
#     "quantalogic",
# ]
# ///

import argparse
import os
from typing import Any

import loguru
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax

from quantalogic import Agent
from quantalogic.console_print_events import console_print_events
from quantalogic.console_print_token import console_print_token
from quantalogic.tools import GenerateDatabaseReportTool, InputQuestionTool, SQLQueryTool
from quantalogic.tools.utils import create_sample_database

# Parse command-line arguments
parser = argparse.ArgumentParser(
    description="Interactive SQL query interface powered by AI",
    epilog="""
Examples:
  python 09-sql-query.py --model deepseek/deepseek-chat
  python 09-sql-query.py --help

Available models:
  - deepseek/deepseek-chat (default)
  - openai/gpt-4o-mini
  - anthropic/claude-3.5-sonnet
  - openrouter/deepseek/deepseek-chat
  - openrouter/mistralai/mistral-large-2411
"""
)
parser.add_argument(
    "--model",
    type=str,
    default="deepseek/deepseek-chat",
    help="Model name to use (default: deepseek/deepseek-chat) or any of the following: openai/gpt-4o-mini, anthropic/claude-3.5-sonnet, openrouter/deepseek/deepseek-chat, openrouter/mistralai/mistral-large-2411",
)
args = parser.parse_args()

MODEL_NAME = args.model

# Using specified model for cost-effectiveness and performance
# Can be switched to OpenAI/Anthropic models if needed for specific use cases
# MODEL_NAME = "deepseek/deepseek-chat"  # Default: Best balance of cost and capability
# Alternative options (uncomment to use):
# MODEL_NAME = "openai/gpt-4o-mini"  # For OpenAI ecosystem compatibility
# MODEL_NAME = "anthropic/claude-3.5-sonnet"  # For advanced reasoning tasks
# MODEL_NAME = "openrouter/deepseek/deepseek-chat"  # Via OpenRouter API
# MODEL_NAME = "openrouter/mistral-large"  # Mistral Large via OpenRouter API

# Verify required API keys
if not os.environ.get("DEEPSEEK_API_KEY"):
    raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

# Database connection configuration
# Prefers environment variable for security (avoids hardcoding credentials)
# Falls back to interactive prompt for local development convenience
# Defaults to SQLite for quick setup and demonstration purposes
console = Console()
db_conn = os.environ.get("DB_CONNECTION_STRING") or Prompt.ask(
    "[bold]Enter database connection string[/bold]", default="sqlite:///sample.db", console=console
)


def get_database_report():
    """Generate a database report using the GenerateDatabaseReportTool."""
    tool = GenerateDatabaseReportTool(connection_string=db_conn)
    return tool.execute()


# Initialize agent with SQL capabilities
def create_agent(connection_string: str) -> Agent:
    """Create an agent with SQL capabilities."""
    agent = Agent(
        model_name=MODEL_NAME,
        tools=[
            SQLQueryTool(connection_string=connection_string),
            InputQuestionTool(),
        ],
    )

    return agent


agent = create_agent(db_conn)

# Event-driven architecture for better observability and control
# Handles key lifecycle events to provide real-time feedback
# Tracks: task states, tool execution, and error conditions
agent.event_emitter.on(
    [
        "task_complete",  # Final task state
        "task_think_start",  # Agent begins processing
        "task_think_end",  # Agent finishes processing
        "tool_execution_start",  # Tool begins execution
        "tool_execution_end",  # Tool completes execution
        "error_max_iterations_reached",  # Safety limit exceeded
    ],
    console_print_events,  # Unified event display handler
)

# Visual feedback system using spinner
# Global state ensures only one spinner runs at a time
current_spinner = None  # Tracks active spinner instance


def start_spinner(event: str, data: Any | None = None) -> None:
    """Start spinner to indicate processing state.
    Uses global state to prevent multiple concurrent spinners.
    """
    global current_spinner
    current_spinner = console.status("[bold green]Analyzing query...[/bold green]", spinner="dots")
    current_spinner.start()


def stop_spinner(event: str, data: Any | None = None) -> None:
    """Cleanly stop spinner and release resources.
    Prevents memory leaks from orphaned spinners.
    """
    global current_spinner
    if current_spinner:
        current_spinner.stop()
        current_spinner = None  # Clear reference to allow garbage collection



# Updated event handling
loguru.logger.info("Registering event listeners")
agent.event_emitter.on("task_solve_start", start_spinner)
agent.event_emitter.on("stream_chunk", stop_spinner)
agent.event_emitter.on("stream_chunk", console_print_token)
agent.event_emitter.on("task_solve_end", stop_spinner)



def format_markdown(result: str) -> Panel:
    """Render markdown content with professional styling."""
    if "```sql" in result:
        result = Syntax(result, "sql", theme="monokai", line_numbers=False)
        return Panel.fit(result, title="Generated SQL", border_style="blue")

    md = Markdown(result, code_theme="dracula", inline_code_theme="dracula", justify="left")
    return Panel.fit(
        md,
        title="[bold]Query Results[/bold]",
        border_style="bright_cyan",
        padding=(1, 2),
        subtitle="📊 Database Results",
    )


def query_loop():
    """Interactive query interface with error recovery.
    Designed for continuous operation with graceful exit handling.
    Provides clear visual feedback and error recovery options.
    """
    console.print(
        Panel.fit(
            "[bold reverse] 💽 SQL QUERY INTERFACE [/bold reverse]",
            border_style="bright_magenta",
            subtitle="Type 'exit' to quit",
        )
    )

    # Getting database report
    console.print("Generating database report...")
    database_report = get_database_report()
    console.print(format_markdown(database_report), width=90)

    while True:
        try:
            question = Prompt.ask("\n[bold cyan]❓ Your question[/bold cyan]")
            if question.lower() in ("exit", "quit", "q"):
                break

            task_description = f"""
            As an expert database analyst, perform these steps:

            1. Analyze the question: "{question}"
            2. Generate appropriate SQL query
            3. Execute the SQL query and present the results

            The database context is as follows, strictly respect it:
            
            {database_report}
            
            """

            result = agent.solve_task(task_description, streaming=True)
            console.print(format_markdown(result), width=90)

            if not Confirm.ask("[bold]Submit another query?[/bold]", default=True):
                break

        except Exception as e:
            console.print(
                Panel.fit(f"[red bold]ERROR:[/red bold] {str(e)}", border_style="red", title="🚨 Processing Error")
            )
            if not Confirm.ask("[bold]Try another question?[/bold]", default=True):
                break

    console.print(
        Panel.fit(
            "[bold green]Session terminated[/bold green]",
            border_style="bright_green",
            subtitle="Thank you for using the SQL interface!",
        )
    )


if __name__ == "__main__":
    create_sample_database("sample.db")
    query_loop()
