from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

console = Console()

def display_response(response: str, title: str, border_style: str, is_error: bool = False) -> None:
    """
    Display a response in a standardized panel format.
    
    Args:
        response: The text to display.
        title: The title of the panel.
        border_style: The color/style of the panel border.
        is_error: If True, treat as an error and force red border.
    """
    if is_error:
        console.print(Panel(response, title=title, border_style="red"))
    else:
        console.print(Panel(Markdown(response), title=title, border_style=border_style))