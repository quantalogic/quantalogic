import os
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax

from quantalogic import Agent
from quantalogic.console_print_events import console_print_events
from quantalogic.console_print_token import console_print_token
from quantalogic.tools import GenerateDatabaseReportTool, InputQuestionTool, LLMTool, SQLQueryTool

MODEL_NAME = "deepseek/deepseek-chat"

# Verify required API keys
if not os.environ.get("DEEPSEEK_API_KEY"):
    raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

# Configure database connection
console = Console()
db_conn = os.environ.get("DB_CONNECTION_STRING") or Prompt.ask(
    "[bold]Enter database connection string[/bold]", default="sqlite:///sample.db", console=console
)

# Initialize agent with SQL capabilities
agent = Agent(
    model_name=MODEL_NAME,
    tools=[
        SQLQueryTool(connection_string=db_conn),
        InputQuestionTool(),
        GenerateDatabaseReportTool(connection_string=db_conn),
        LLMTool(model_name=MODEL_NAME, on_token=console_print_token),
    ],
)

# Set up event handlers
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

# Store spinner reference and control state
current_spinner = None

def start_spinner(event: str, data: Any | None = None) -> None:
    """Start a spinner for query processing."""
    global current_spinner
    current_spinner = console.status("[bold green]Analyzing query...[/bold green]", spinner="dots")
    current_spinner.start()

def stop_spinner(event: str, data: Any | None = None) -> None:
    """Stop the active spinner."""
    global current_spinner
    if current_spinner:
        current_spinner.stop()
        current_spinner = None

# Updated event handling
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

def get_database_report():
    """Generate a database report using the GenerateDatabaseReportTool."""
    tool = GenerateDatabaseReportTool(connection_string=db_conn)
    return tool.execute()

def query_loop():
    """Interactive loop for natural language database queries."""
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

            The database context is as follows:
            
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
    query_loop()