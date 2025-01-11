"""Print events with rich formatting."""

from typing import Any

from rich.console import Console


def console_print_token(event: str, data: Any | None = None):
    """Print a token with rich formatting.
    
    Args:
        event (str): The event name (e.g., 'stream_chunk')
        data (Any | None): The token data to print
    """
    console = Console()
    console.print(data, end="")
