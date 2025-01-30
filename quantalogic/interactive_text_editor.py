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
    console.print(f"[bold #ffaa00]Current datetime: {datetime.now().isoformat()}[/bold #ffaa00]")

@registry.register("/edit", "Edit specific line: /edit <line_number>")
def handle_edit_command(lines: List[str], args: List[str], console: Console,
                      session: PromptSession, history_manager: InputHistoryManager) -> None:
    """Edit a specific line in the input buffer."""
    try:
        edit_line_num = int(args[0]) - 1
        if 0 <= edit_line_num < len(lines):
            console.print(f"[bold #1d3557]Editing Line {edit_line_num + 1}:[/bold #1d3557] {lines[edit_line_num]}")  # Dark blue
            new_line = session.prompt("New content: ")
            history_manager.push_state(lines)
            lines[edit_line_num] = new_line
        else:
            console.print("[bold #ff4444]Invalid line number.[/bold #ff4444]")
    except (ValueError, IndexError):
            console.print("[bold #ff4444]Invalid edit command. Usage: /edit <line_number>[/bold #ff4444]")

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
            console.print("[bold #ff4444]Invalid delete command. Usage: /delete <line_number>[/bold #ff4444]")

@registry.register("/replace", "Search and replace: /replace <search> <replace>")
def handle_replace_command(lines: List[str], args: List[str], console: Console,
    session: PromptSession, history_manager: InputHistoryManager) -> None:
    try:
        search_str = args[0]
        replace_str = args[1]
        history_manager.push_state(lines)
        for i in range(len(lines)):
            lines[i] = lines[i].replace(search_str, replace_str)
            console.print("[bold #00cc66]Search and replace completed.[/bold #00cc66]")
    except (ValueError, IndexError):
            console.print("[bold #ff4444]Invalid replace command. Usage: /replace <search_str> <replace_str>[/bold #ff4444]")

@registry.register("/model", "Show current AI model") 
def handle_model_command(lines: List[str], args: List[str], console: Console,
    session: PromptSession, history_manager: InputHistoryManager) -> None:
    from quantalogic.agent_factory import AgentRegistry
    try:
        current_agent = AgentRegistry.get_agent("main_agent")
        if current_agent:
            console.print(f"[bold #ffaa00]Current AI model: {current_agent.model_name}[/bold #ffaa00]")
        else:
            console.print("[bold #ffaa00]No active agent found.[/bold #ffaa00]")
    except ValueError as e:
            console.print(f"[bold #ff4444]Error: {str(e)}[/bold #ff4444]")

@registry.register("/setmodel", "Set AI model name: /setmodel <name>")
def handle_set_model_command(lines: List[str], args: List[str], console: Console,
    session: PromptSession, history_manager: InputHistoryManager) -> None:
    from quantalogic.agent_factory import AgentRegistry
    try:
        if len(args) < 1:
            console.print("[bold #ff4444]Error: Model name required. Usage: /setmodel <name>[/bold #ff4444]")
            return
            
        model_name = args[0]
        current_agent = AgentRegistry.get_agent("main_agent")
        if current_agent:
            current_agent.model_name = model_name
            console.print(f"[bold #00cc66]Model name updated to: {model_name}[/bold #00cc66]")
        else:
            console.print("[yellow]No active agent found.[/yellow]")
    except ValueError as e:
        console.print(f"[red]Error: {str(e)}[/red]")

@registry.register("/models", "List all available AI models")
def handle_models_command(lines: List[str], args: List[str], console: Console,
    session: PromptSession, history_manager: InputHistoryManager) -> None:
    """Display all available AI models supported by the system."""
    from quantalogic.utils.get_all_models import get_all_models
    try:
        models = get_all_models()
        if models:
            # Group models by provider
            provider_groups = {}
            for model in models:
                provider = model.split('/')[0] if '/' in model else 'default'
                if provider not in provider_groups:
                    provider_groups[provider] = []
                provider_groups[provider].append(model)
            
            # Create formatted output
            output = "[bold #00cc66]Available AI Models:[/bold #00cc66]\n"
            for provider, model_list in provider_groups.items():
                output += f"\n[bold #ffaa00]{provider.upper()}[/bold #ffaa00]\n"
                for model in sorted(model_list):
                    output += f"  • {model}\n"
            
            console.print(Panel(output, border_style="green"))
        else:
            console.print("[yellow]No models available.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error retrieving models: {str(e)}[/red]")


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
            console.print("[bold #00cc66]Undo successful.[/bold #00cc66]")


    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.styles import Style
    
    class CommandCompleter(Completer):
        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            line_parts = text.split()
            
            if len(line_parts) == 0 or (len(line_parts) == 1 and text.endswith(' ')):
                for cmd, details in registry.commands.items():
                    yield Completion(
                        cmd,
                        start_position=-len(text),
                        display=f"[{cmd}] {details['help']}",
                        style="fg:ansicyan bold",
                    )
            elif line_parts[0] in registry.commands:
                cmd = registry.commands[line_parts[0]]
                arg_index = len(line_parts) - 1
                if arg_index == 1:
                    doc = cmd['handler'].__doc__ or ""
                    args_hint = next((line.split(':')[1].strip() for line in doc.split('\n') 
                                    if 'Args:' in line), "")
                    if args_hint:
                        yield Completion(
                            f"<{args_hint}>",
                            start_position=-len(text.split()[-1]),
                            style="fg:ansimagenta italic",
                            display=f"Expected argument: {args_hint}",
                        )
            else:
                if text.startswith('/'):
                    partial = text[1:].lstrip('/')
                    exact_matches = []
                    prefix_matches = []
                    
                    for cmd in registry.commands:
                        cmd_without_slash = cmd[1:]
                        if cmd_without_slash.lower() == partial.lower():
                            exact_matches.append(cmd)
                        elif cmd_without_slash.lower().startswith(partial.lower()):
                            prefix_matches.append(cmd)
                    
                    # Prioritize exact matches first
                    for match in exact_matches:
                        remaining = match[len('/' + partial):]
                        yield Completion(
                            remaining,
                            start_position=0,  # Corrected from -len(partial)
                            display=f"{match} - {registry.commands[match]['help']}",
                            style="fg:ansiyellow bold",
                        )
                    
                    # Then prefix matches
                    for match in prefix_matches:
                        remaining = match[len('/' + partial):]
                        yield Completion(
                            remaining,
                            start_position=0,  # Corrected from -len(partial)
                            display=f"{match} - {registry.commands[match]['help']}",
                            style="fg:ansiyellow bold",
                        )
            def get_completions(self, document, complete_event):
                text = document.text_before_cursor
                line_parts = text.split()
                
                if len(line_parts) == 0 or (len(line_parts) == 1 and text.endswith(' ')):
                    for cmd, details in registry.commands.items():
                        yield Completion(
                            cmd,
                            start_position=-len(text),
                            display=f"[{cmd}] {details['help']}",
                            style="fg:ansicyan bold",
                        )
                elif line_parts[0] in registry.commands:
                    cmd = registry.commands[line_parts[0]]
                    arg_index = len(line_parts) - 1
                    if arg_index == 1:
                        doc = cmd['handler'].__doc__ or ""
                        args_hint = next((line.split(':')[1].strip() for line in doc.split('\n') 
                                        if 'Args:' in line), "")
                        if args_hint:
                            yield Completion(
                                f"<{args_hint}>",
                                start_position=-len(text.split()[-1]),
                                style="fg:ansimagenta italic",
                                display=f"Expected argument: {args_hint}",
                            )
                else:
                    if text.startswith('/'):
                        partial = text[1:].lstrip('/')
                        exact_matches = []
                        prefix_matches = []
                        
                        for cmd in registry.commands:
                            cmd_without_slash = cmd[1:]
                            if cmd_without_slash.lower() == partial.lower():
                                exact_matches.append(cmd)
                            elif cmd_without_slash.lower().startswith(partial.lower()):
                                prefix_matches.append(cmd)
                        
                        for match in exact_matches:
                            remaining = match[len('/' + partial):]
                            yield Completion(
                                remaining,
                                start_position=-len(partial),
                                display=f"{match} - {registry.commands[match]['help']}",
                                style="fg:ansiyellow bold",
                            )
                        
                        for match in prefix_matches:
                            remaining = match[len('/' + partial):]
                            yield Completion(
                                remaining,
                                start_position=-len(partial),
                                display=f"{match} - {registry.commands[match]['help']}",
                                style="fg:ansiyellow bold",
                            )

    command_completer = CommandCompleter()
    
    def get_command_help(cmd_name: str) -> str:
        """Get formatted help text for a command"""
        if cmd := registry.commands.get(cmd_name):
            return f"[bold]{cmd_name}[/bold]: {cmd['help']}\n{cmd['handler'].__doc__ or ''}"
        return ""

    custom_style = Style.from_dict({
        'completion-menu.completion': 'bg:#005577 #ffffff',
        'completion-menu.completion.current': 'bg:#007799 #ffffff bold',
        'scrollbar.background': 'bg:#6699aa',
        'scrollbar.button': 'bg:#444444',
        'documentation': 'bg:#003366 #ffffff',
    })

    session = PromptSession(
        history=InMemoryHistory(),
        auto_suggest=AutoSuggestFromHistory(),
        key_bindings=bindings,
        completer=command_completer,
        complete_while_typing=True,
        style=custom_style,
        bottom_toolbar=lambda: get_command_help(session.default_buffer.document.text.split()[0][1:] 
                                              if session.default_buffer.document.text.startswith('/') 
                                              else ""),
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