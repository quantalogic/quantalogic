"""Module for checking and displaying version updates."""

import random

from rich.console import Console
from rich.panel import Panel

from quantalogic.utils.check_version import check_if_is_latest_version
from quantalogic.version import get_version


def check_new_version() -> None:
    """Randomly check for updates and display a notification if a new version is available.

    This function has a 1 in 10 chance of running when called. When it runs, it checks
    if there's a newer version of the package available and displays an update panel
    with installation instructions if a new version is found.
    """
    # Randomly check for updates (1 in 10 chance)
    if random.randint(1, 10) == 1:
        try:
            current_version = get_version()
            has_new_version, latest_version = check_if_is_latest_version()

            if has_new_version:
                console = Console()
                console.print(
                    Panel.fit(
                        f"[yellow]⚠️  Update Available![/yellow]\n\n"
                        f"Current version: [bold]{current_version}[/bold]\n"
                        f"Latest version: [bold]{latest_version}[/bold]\n\n"
                        "To update, run:\n"
                        "[bold]pip install --upgrade quantalogic[/bold]\n"
                        "or if using pipx:\n"
                        "[bold]pipx upgrade quantalogic[/bold]",
                        title="[bold]Update Available[/bold]",
                        border_style="yellow",
                    )
                )
        except Exception:
            return
