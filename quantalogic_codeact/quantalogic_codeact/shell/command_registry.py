from typing import Callable, Dict, List, Optional


class CommandRegistry:
    """Manages registration and storage of shell commands."""
    def __init__(self):
        self.commands: Dict[str, Dict[str, Callable | str | Optional[List[str]]]] = {}

    def register(self, name: str, func: Callable, help_text: str, args: Optional[List[str]] = None) -> None:
        """Register a new command with optional arguments for autocompletion.

        Args:
            name: The name of the command (without the leading '/').
            func: The function to execute when the command is called.
            help_text: A description of the command and its usage.
            args: Optional list of possible arguments for autocompletion.
        """
        self.commands[name] = {
            "func": func, 
            "help": help_text, 
            "args": args,
            "get_completions": lambda document, complete_event: args or []
        }