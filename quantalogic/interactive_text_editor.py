from typing import List

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.panel import Panel


class InputHistoryManager:
    def __init__(self):
        self.history_stack = []
        self.current_state = []

    def push_state(self, lines: List[str]) -> None:
        self.history_stack.append(self.current_state.copy())
        self.current_state = lines.copy()

    def undo(self, lines: List[str]) -> bool:
        if self.history_stack:
            self.current_state = self.history_stack.pop()
            lines[:] = self.current_state
            return True
        return False

class CommandRegistry:
    def __init__(self):
        self.commands = {}
        
    def register(self, name: str, help_text: str = "") -> callable:
        def decorator(func: callable) -> callable:
            self.commands[name] = {
                "handler": func,
                "help": func.__doc__ or help_text
            }
            return func
        return decorator

registry = CommandRegistry()

@registry.register("/help", "Show available commands")
def handle_help_command(lines: List[str], args: List[str], console: Console, 
                      session: PromptSession, history_manager: InputHistoryManager) -> None:
    """Display auto-generated help from registered commands."""
    help_content = "\n".join([f"  {name}: {cmd['help']}" for name, cmd in registry.commands.items()])
    console.print(Panel(f"Available commands:\n{help_content}", title="Help Menu", border_style="green"))

@registry.register("/date", "Show current date/time")
def handle_date_command(lines: List[str], args: List[str], console: Console,
                      session: PromptSession, history_manager: InputHistoryManager) -> None:
    """Display current date and time."""
    from datetime import datetime
    console.print(f"[yellow]Current datetime: {datetime.now().isoformat()}[/yellow]")

@registry.register("/edit", "Edit specific line: /edit <line_number>")
def handle_edit_command(lines: List[str], args: List[str], console: Console,
                      session: PromptSession, history_manager: InputHistoryManager) -> None:
    """Edit a specific line in the input buffer."""
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
        console.print("[red]Invalid edit command. Usage: /edit <line_number>[/red]")

@registry.register("/delete", "Delete specific line: /delete <line_number>")
def handle_delete_command(lines: List[str], args: List[str], console: Console,
                        session: PromptSession, history_manager: InputHistoryManager) -> None:
    """Delete a specific line from the input buffer."""
    try:
        delete_line_num = int(args[0]) - 1
        if 0 <= delete_line_num < len(lines):
            history_manager.push_state(lines)
            lines.pop(delete_line_num)
            console.print(f"[bold]Deleted Line {delete_line_num + 1}[/bold]")
        else:
            console.print("[red]Invalid line number.[/red]")
    except (ValueError, IndexError):
        console.print("[red]Invalid delete command. Usage: /delete <line_number>[/red]")

@registry.register("/replace", "Search and replace: /replace <search> <replace>")
def handle_replace_command(lines: List[str], args: List[str], console: Console,
    session: PromptSession, history_manager: InputHistoryManager) -> None:
    try:
        search_str = args[0]
        replace_str = args[1]
        history_manager.push_state(lines)
        for i in range(len(lines)):
            lines[i] = lines[i].replace(search_str, replace_str)
        console.print("[bold]Search and replace completed.[/bold]")
    except (ValueError, IndexError):
        console.print("[red]Invalid replace command. Usage: /replace <search_str> <replace_str>[/red]")

@registry.register("/model", "Show current AI model") 
def handle_model_command(lines: List[str], args: List[str], console: Console,
    session: PromptSession, history_manager: InputHistoryManager) -> None:
    from quantalogic.agent_factory import AgentRegistry
    try:
        current_agent = AgentRegistry.get_agent("main_agent")
        if current_agent:
            console.print(f"[yellow]Current AI model: {current_agent.model_name}[/yellow]")
        else:
            console.print("[yellow]No active agent found.[/yellow]")
    except ValueError as e:
        console.print(f"[red]Error: {str(e)}[/red]")

@registry.register("/setmodel", "Set AI model name: /setmodel <name>")
def handle_set_model_command(lines: List[str], args: List[str], console: Console,
    session: PromptSession, history_manager: InputHistoryManager) -> None:
    from quantalogic.agent_factory import AgentRegistry
    try:
        if len(args) < 1:
            console.print("[red]Error: Model name required. Usage: /setmodel <name>[/red]")
            return
            
        model_name = args[0]
        current_agent = AgentRegistry.get_agent("main_agent")
        if current_agent:
            current_agent.model_name = model_name
            console.print(f"[green]Model name updated to: {model_name}[/green]")
        else:
            console.print("[yellow]No active agent found.[/yellow]")
    except ValueError as e:
        console.print(f"[red]Error: {str(e)}[/red]")


def get_multiline_input(console: Console) -> str:
    """Get multiline input with slash command support."""
    console.print(
        Panel(
            "Enter your task. Press [bold]Enter[/bold] twice to submit.\n"
            "Type /help for available commands",
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

    import re

    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.styles import Style
    
    class CommandCompleter(Completer):
        def get_completions(self, document, complete_event):
            pattern = re.compile(r'(?<!\S)/\w*')  # Match /commands with word boundary
            word = document.get_word_before_cursor(pattern=pattern)
            if word.startswith('/'):
                for cmd, details in registry.commands.items():
                    if cmd.startswith(word[1:]):
                        yield Completion(
                            cmd,
                            start_position=-len(word),
                            display=f"{cmd} - {details['help']}",
                            style="fg:ansiyellow bold",
                        )

    command_completer = CommandCompleter()
    
    custom_style = Style.from_dict({
        'completion-menu.completion': 'bg:#008888 #ffffff',
        'completion-menu.completion.current': 'bg:#00aaaa #000000 bold',
        'scrollbar.background': 'bg:#88aaaa',
        'scrollbar.button': 'bg:#222222',
    })
    
    session = PromptSession(
        history=InMemoryHistory(),
        auto_suggest=AutoSuggestFromHistory(),
        key_bindings=bindings,
        completer=command_completer,
        complete_while_typing=True,
        style=custom_style
    )

    try:
        while True:
            prompt_text = f"{line_number:>3}: "
            line = session.prompt(prompt_text, rprompt="Press Enter twice to submit")

            if line.strip().startswith('/'):
                cmd_parts = line.strip().split()
                cmd_name = cmd_parts[0].lower()
                args = cmd_parts[1:]
                
                if cmd_handler := registry.commands.get(cmd_name):
                    try:
                        cmd_handler["handler"](lines, args, console, session, history_manager)
                    except Exception as e:
                        console.print(f"[red]Error executing {cmd_name}: {str(e)}[/red]")
                else:
                    console.print(f"[red]Unknown command: {cmd_name}[/red]")
                continue

            if line.strip() == "":
                blank_lines += 1
                if blank_lines == 2:
                    break
            else:
                blank_lines = 0
                if not any(line.strip().startswith(cmd) for cmd in registry.commands):
                    history_manager.push_state(lines)
                    lines.append(line)
                    line_number += 1
    except EOFError:
        console.print("\n[bold]Input terminated.[/bold]")
    except KeyboardInterrupt:
        console.print("\n[bold]Input cancelled by user.[/bold]")
        return ""

    return "\n".join(lines)