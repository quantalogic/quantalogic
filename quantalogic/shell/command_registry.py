"""Command registry for shell commands."""
from typing import Callable, Dict


class CommandRegistry:
    """Manages registration and storage of shell commands."""
    def __init__(self):
        self.commands: Dict[str, Dict[str, Callable | str]] = {}

    def register(self, name: str, func: Callable, help_text: str) -> None:
        """Register a new command."""
        self.commands[name] = {"func": func, "help": help_text}
