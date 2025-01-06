"""Utility functions for the QuantaLogic AI Assistant."""

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.panel import Panel


class InputHistoryManager:
    """Manages the history of input states for undo functionality."""

    def __init__(self):
        """Initialize the InputHistoryManager with an empty history stack and current state."""
        self.history_stack = []
        self.current_state = []

    def push_state(self, lines):
        """Push the current state to the history stack and update the current state.

        Args:
            lines (list): The current lines of input to be saved in the history.
        """
        self.history_stack.append(self.current_state.copy())
        self.current_state = lines.copy()

    def undo(self, lines):
        """Revert to the previous state from the history stack.

        Args:
            lines (list): The current lines of input to be updated to the previous state.

        Returns:
            bool: True if undo was successful, False otherwise.
        """
        if self.history_stack:
            self.current_state = self.history_stack.pop()
            lines[:] = self.current_state
            return True
        return False


def handle_edit_command(lines, args, console, session, history_manager):
    """Handle the 'edit' command to modify a specific line.

    Args:
        lines (list): The current lines of input.
        args (list): The arguments provided with the command.
        console (Console): The console object for output.
        session (PromptSession): The prompt session for user input.
        history_manager (InputHistoryManager): The history manager for state tracking.
    """
    try:
        edit_line_num = int(args[0]) - 1
        if 0 <= edit_line_num < len(lines):
            console.print(f"[bold]Editing Line {edit_line_num + 1}:[/bold] {lines[edit_line_num]}")
            new_line = session.prompt("New content: ")
            history_manager.push_state(lines)
            lines[edit_line_num] = new_line
        else:
            console.print("[red]Invalid line number.[/red]")
    except (ValueError, IndexError):
        console.print("[red]Invalid edit command. Usage: edit <line_number>[/red]")


def handle_delete_command(lines, args, console, history_manager):
    """Handle the 'delete' command to remove a specific line.

    Args:
        lines (list): The current lines of input.
        args (list): The arguments provided with the command.
        console (Console): The console object for output.
        history_manager (InputHistoryManager): The history manager for state tracking.
    """
    try:
        delete_line_num = int(args[0]) - 1
        if 0 <= delete_line_num < len(lines):
            history_manager.push_state(lines)
            lines.pop(delete_line_num)
            console.print(f"[bold]Deleted Line {delete_line_num + 1}[/bold]")
        else:
            console.print("[red]Invalid line number.[/red]")
    except (ValueError, IndexError):
        console.print("[red]Invalid delete command. Usage: delete <line_number>[/red]")


def handle_replace_command(lines, args, console, history_manager):
    """Handle the 'replace' command to search and replace text in all lines.

    Args:
        lines (list): The current lines of input.
        args (list): The arguments provided with the command.
        console (Console): The console object for output.
        history_manager (InputHistoryManager): The history manager for state tracking.
    """
    try:
        search_str, replace_str = args
        history_manager.push_state(lines)
        for i in range(len(lines)):
            lines[i] = lines[i].replace(search_str, replace_str)
        console.print("[bold]Search and replace completed.[/bold]")
    except ValueError:
        console.print("[red]Invalid replace command. Usage: replace <search_str> <replace_str>[/red]")


commands = {"edit": handle_edit_command, "delete": handle_delete_command, "replace": handle_replace_command}


def handle_command(line, lines, console, session, history_manager):
    """Handle a command entered by the user.

    Args:
        line (str): The command line entered by the user.
        lines (list): The current lines of input.
        console (Console): The console object for output.
        session (PromptSession): The prompt session for user input.
        history_manager (InputHistoryManager): The history manager for state tracking.

    Returns:
        bool: True if the command was handled, False otherwise.
    """
    parts = line.split()
    if not parts:
        return False
    command = parts[0]
    args = parts[1:]
    if command in commands:
        commands[command](lines, args, console, session, history_manager)
        return True
    return False


def get_multiline_input(console: Console) -> str:
    """Get multiline input from the user with enhanced UX.

    Args:
        console (Console): The console object for output.

    Returns:
        str: The multiline input provided by the user.
    """
    console.print(
        Panel(
            "Enter your task. Press [bold]Enter[/bold] twice to submit.\n"
            "Available commands:\n"
            "  edit <line_number> - Edit a specific line\n"
            "  delete <line_number> - Delete a specific line\n"
            "  replace <search_str> <replace_str> - Replace text in all lines",
            title="Multi-line Input",
            border_style="blue",
        )
    )

    lines = []
    history_manager = InputHistoryManager()
    blank_lines = 0
    line_number = 1

    bindings = KeyBindings()

    @bindings.add("c-z")
    def _(event):
        if history_manager.undo(lines):
            console.print("[bold]Undo successful.[/bold]")

    session = PromptSession(history=InMemoryHistory(), auto_suggest=AutoSuggestFromHistory(), key_bindings=bindings)

    try:
        while True:
            prompt_text = f"{line_number:>3}: "
            line = session.prompt(prompt_text, rprompt="Press Enter twice to submit")

            if line.strip() == "":
                blank_lines += 1
                if blank_lines == 2:
                    break
            else:
                blank_lines = 0
                if not handle_command(line, lines, console, session, history_manager):
                    history_manager.push_state(lines)
                    lines.append(line)
                    line_number += 1
    except EOFError:
        console.print("\n[bold]Input terminated.[/bold]")
    except KeyboardInterrupt:
        console.print("\n[bold]Input cancelled by user.[/bold]")
        return ""

    return "\n".join(lines)
