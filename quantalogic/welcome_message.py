"""Module for displaying welcome messages and instructions."""

from rich.console import Console
from rich.panel import Panel


def create_config_table(
    mode: str,
    model_name: str,
    vision_model_name: str | None,
    max_iterations: int,
    compact_every_n_iteration: int | None,
    max_tokens_working_memory: int | None,
) -> str:
    """Create a formatted string representation of the configuration table."""
    return (
        f"• Mode              [cyan]{mode}[/cyan]\n"
        f"• Language Model    [cyan]{model_name}[/cyan]\n"
        f"• Vision Model      {vision_model_name or '[dim]Not Configured[/dim]'}\n"
        f"• Max Iterations    {max_iterations}\n"
        f"• Memory Compaction {compact_every_n_iteration or '[dim]Default[/dim]'}\n"
        f"• Max Memory Tokens {max_tokens_working_memory or '[dim]Default[/dim]'}"
    )


def create_tips_section() -> str:
    """Create a formatted string representation of the tips section."""
    return (
        "💡 [bold cyan]Be specific[/bold cyan] in your task descriptions\n"
        "💭 Use [bold cyan]clear and concise[/bold cyan] language\n"
        "✨ Include [bold cyan]relevant context[/bold cyan] for coding tasks\n"
        "🚀 Don't hesitate to ask [bold cyan]challenging questions[/bold cyan]!"
    )


def display_welcome_message(
    console: Console,
    model_name: str, 
    version: str,
    vision_model_name: str | None = None, 
    max_iterations: int = 50, 
    compact_every_n_iteration: int | None = None,
    max_tokens_working_memory: int | None = None,
    mode: str = "basic",
) -> None:
    """Display a welcome message and instructions for the QuantaLogic AI Assistant.
    
    Args:
        console: Rich Console instance for rendering output
        model_name: Name of the language model being used
        version: Version of the QuantaLogic AI Assistant
        vision_model_name: Optional name of the vision model
        max_iterations: Maximum number of iterations for task solving
        compact_every_n_iteration: Frequency of memory compaction
        max_tokens_working_memory: Maximum tokens allowed in working memory
        mode: Current agent mode of operation
    """
    config_section = create_config_table(
        mode,
        model_name,
        vision_model_name,
        max_iterations,
        compact_every_n_iteration,
        max_tokens_working_memory,
    )
    
    tips_section = create_tips_section()

    welcome_content = (
        "\n[bold violet]Welcome to QuantaLogic AI Assistant[/bold violet]  "
        f"[bold blue]v{version}[/bold blue]\n\n"
        "[bold]System Configuration[/bold]\n"
        f"{config_section}\n\n"
        "[bold magenta]Pro Tips[/bold magenta]\n"
        f"{tips_section}\n"
    )
    
    welcome_panel = Panel(
        welcome_content,
        border_style="blue",
        title="[bold]🤖 QuantaLogic[/bold]",
        subtitle="[bold cyan]Ready to assist you[/bold cyan]",
        padding=(1, 2),
    )
    
    console.print(welcome_panel)
