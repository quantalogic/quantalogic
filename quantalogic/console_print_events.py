from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree


def console_print_events(event: str, data: dict[str, Any] | None = None):
    """Print events with rich formatting.

    Args:
        event (str): Name of the event.
        data (Dict[str, Any], optional): Additional event data. Defaults to None.
    """
    console = Console()

    # Define panel title with enhanced styling
    panel_title = f"[bold cyan]Event: {event}[/bold cyan]"

    if not data:
        # Display a friendly message when no data is available
        console.print(
            Panel(
                "[italic yellow]No additional event data available.[/italic yellow]",
                title=panel_title,
                border_style="dim",
                expand=True,
                padding=(1, 2),
            )
        )
        return

    # Function to render nested dictionaries as a tree
    def render_tree(data: dict[str, any], tree: Tree):
        for key, value in data.items():
            if isinstance(value, dict):
                branch = tree.add(f"[bold magenta]{key}[/bold magenta]")
                render_tree(value, branch)
            elif isinstance(value, list):
                branch = tree.add(f"[bold magenta]{key}[/bold magenta]")
                for index, item in enumerate(value, start=1):
                    if isinstance(item, dict):
                        sub_branch = branch.add(f"[cyan]Item {index}[/cyan]")
                        render_tree(item, sub_branch)
                    else:
                        branch.add(f"[green]{item}[/green]")
            else:
                tree.add(f"[bold yellow]{key}[/bold yellow]: [white]{value}[/white]")

    # Create a Tree to represent nested data
    tree = Tree(f"[bold blue]{event} Details[/bold blue]", guide_style="bold bright_blue")

    render_tree(data, tree)

    # Create a panel to display the tree
    panel = Panel(
        tree,
        title=panel_title,
        border_style="bright_blue",
        padding=(1, 2),
        box=box.ROUNDED,
        expand=True,
    )

    console.print(panel)