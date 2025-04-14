import asyncio
from importlib.metadata import entry_points
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import NestedCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from rich import print as rprint
from rich.markdown import Markdown
from rich.panel import Panel

from quantalogic.codeact.agent import Agent, AgentConfig
from quantalogic.codeact.events import StreamTokenEvent

from .command_registry import CommandRegistry
from .commands import (
    chat_command,
    clear_command,
    exit_command,
    help_command,
    history_command,
    mode_command,
    solve_command,
    stream_command,
)


class Shell:
    """Interactive CLI shell for dialog with Quantalogic agents."""
    def __init__(self, agent_config: Optional[AgentConfig] = None):
        self.agent = Agent(config=agent_config or AgentConfig())
        self.agent.add_observer(self._stream_token_observer, ["StreamToken"])
        self.message_history: List[Dict[str, str]] = []
        self.streaming: bool = True
        self.mode: str = "codeact"
        self.command_registry = CommandRegistry()
        self._register_builtin_commands()
        self._load_plugin_commands()

    def _register_builtin_commands(self) -> None:
        """Register all built-in commands with their arguments for autocompletion."""
        self.command_registry.register(
            "help",
            lambda args: help_command(self, args),
            "Show help for commands: /help [command]",
            args=None  # Will be set to command list after registration
        )
        self.command_registry.register(
            "chat",
            lambda args: chat_command(self, args),
            "Chat with the agent: /chat <message>",
            args=None  # Free-form input, no specific suggestions
        )
        self.command_registry.register(
            "solve",
            lambda args: solve_command(self, args),
            "Solve a task: /solve <task>",
            args=None  # Free-form input
        )
        self.command_registry.register(
            "exit",
            lambda args: exit_command(self, args),
            "Exit the shell: /exit",
            args=[]  # No arguments expected
        )
        self.command_registry.register(
            "history",
            lambda args: history_command(self, args),
            "Show conversation history: /history",
            args=[]  # No arguments
        )
        self.command_registry.register(
            "clear",
            lambda args: clear_command(self, args),
            "Clear conversation history: /clear",
            args=[]  # No arguments
        )
        self.command_registry.register(
            "stream",
            lambda args: stream_command(self, args),
            "Toggle streaming: /stream on|off",
            args=["on", "off"]  # Specific argument options
        )
        self.command_registry.register(
            "mode",
            lambda args: mode_command(self, args),
            "Set or show the current mode: /mode [react|codeact]",
            args=["react", "codeact"]  # Specific argument options
        )
        # Set args for /help to include all command names for autocompletion
        self.command_registry.commands["help"]["args"] = list(self.command_registry.commands.keys())

    def _load_plugin_commands(self) -> None:
        """Load plugin commands from entry points."""
        try:
            eps = entry_points(group="quantalogic.shell.commands")
            for ep in eps:
                try:
                    cmd_func = ep.load()
                    self.command_registry.register(ep.name, cmd_func, f"Plugin command: {ep.name}", args=None)
                except Exception as e:
                    logger.error(f"Failed to load plugin command {ep.name}: {e}")
        except Exception as e:
            logger.error(f"Error retrieving shell command entry points: {e}")

    async def _stream_token_observer(self, event: object) -> None:
        """Observer for streaming tokens."""
        if isinstance(event, StreamTokenEvent) and self.streaming:
            rprint(event.token, end="", flush=True)

    async def run(self) -> None:
        """Run the interactive shell loop."""
        history_file = Path.home() / ".quantalogic_shell_history"
        kb = KeyBindings()

        @kb.add('enter')
        def _(event):
            event.app.current_buffer.validate_and_handle()

        @kb.add(Keys.ControlJ)
        def _(event):
            event.app.current_buffer.insert_text('\n')

        # Set up autocompletion with command arguments
        completer = NestedCompleter.from_nested_dict({
            f'/{cmd}': (
                {arg: None for arg in info["args"]} 
                if info["args"] and isinstance(info["args"], list) 
                else None
            )
            for cmd, info in self.command_registry.commands.items()
        })
        session = PromptSession(
            message=f"[{self.agent.name or 'Agent'}]> ",
            completer=completer,
            multiline=False,  # Single-line input, Ctrl+J for newlines
            history=FileHistory(str(history_file)),
            key_bindings=kb
        )

        # Welcome message with rich formatting
        welcome_message = (
            f"Welcome to Quantalogic Shell.\n\n"
            f"Mode: {self.mode} - plain messages are "
            f"{'tasks to solve' if self.mode == 'codeact' else 'chat messages'}.\n\n"
            f"Type /help for commands. Press Enter to send, Ctrl+J for new lines."
        )
        rprint(Panel(welcome_message, title="Quantalogic Shell", border_style="blue"))

        while True:
            try:
                user_input = await session.prompt_async()
                user_input = user_input.strip()
                if not user_input:
                    continue

                if user_input.startswith('/'):
                    command_input = user_input[1:].strip()
                    if not command_input:
                        rprint("[red]Error: No command provided. Try /help.[/red]")
                        continue
                    parts = command_input.split(maxsplit=1)
                    command_name = parts[0]
                    args = [parts[1]] if len(parts) > 1 else []
                    if command_name in self.command_registry.commands:
                        result = await self.command_registry.commands[command_name]["func"](args)
                        if result:
                            if command_name == "chat":
                                rprint(Markdown(result))
                            elif command_name == "solve":
                                rprint(Panel(Markdown(result), title="Final Answer", border_style="green"))
                            else:
                                rprint(Panel(result, title=f"{command_name.capitalize()} Command", border_style="blue"))
                    else:
                        rprint(f"[red]Unknown command: /{command_name}. Try /help.[/red]")
                else:
                    # Handle non-command input based on mode
                    if self.mode == "codeact":
                        result = await solve_command(self, [user_input])
                        if result:
                            rprint(Panel(Markdown(result), title="Final Answer", border_style="green"))
                    else:  # react mode
                        result = await chat_command(self, [user_input])
                        if result:
                            rprint(Markdown(result))

            except KeyboardInterrupt:
                rprint("\nUse '/exit' to quit the shell.")
            except SystemExit:
                rprint("Goodbye!")
                break
            except Exception as e:
                rprint(f"[red]Error: {e}[/red]")

def main() -> None:
    shell = Shell()
    asyncio.run(shell.run())

if __name__ == "__main__":
    main()