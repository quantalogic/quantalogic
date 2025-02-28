from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree


def console_print_events(event: str, data: dict[str, Any] | None = None):
    """Print events with elegant compact formatting."""
    console = Console()

    # Stylish no-data presentation
    if not data:
        console.print(
            Panel.fit(
                Text("ⓘ No event data", justify="center", style="italic cyan"),
                title=f"✨ {event}",
                border_style="cyan",
                box=box.ROUNDED,
                padding=(0, 2),
            )
        )
        return

    # Enhanced tree rendering with subtle decorations
    def render_tree(data: dict[str, Any], tree: Tree) -> None:
        for key, value in data.items():
            key_text = Text(f"◈ {key}", style="bright_magenta")
            if isinstance(value, dict):
                branch = tree.add(key_text)
                render_tree(value, branch)
            elif isinstance(value, list):
                branch = tree.add(key_text)
                for item in value:
                    if isinstance(item, dict):
                        sub_branch = branch.add(Text("○", style="cyan"))
                        render_tree(item, sub_branch)
                    else:
                        branch.add(Text(f"• {item}", style="dim green"))
            else:
                tree.add(Text.assemble(key_text, (" → ", "dim"), str(value), style="bright_white"))

    # Create a compact tree with subtle styling
    tree = Tree("", guide_style="dim cyan", hide_root=True)
    render_tree(data, tree)

    # Elegant panel design
    console.print(
        Panel(
            tree,
            title=f"🎯 [bold bright_cyan]{event}[/]",
            border_style="bright_blue",
            box=box.DOUBLE_EDGE,
            padding=(0, 1),
            subtitle=f"[dim]Items: {len(data)}[/dim]",
            subtitle_align="right",
        ),
        no_wrap=True,
    )
