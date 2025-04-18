import sys
from importlib.metadata import entry_points
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import NestedCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from rich.console import Console
from rich.panel import Panel

from ..codeact.agent import Agent, AgentConfig
from .agent_state import AgentState
from .command_registry import CommandRegistry
from .commands.chat import chat_command
from .commands.clear import clear_command
from .commands.exit import exit_command
from .commands.help import help_command
from .commands.history import history_command
from .commands.loglevel import loglevel_command
from .commands.mode import mode_command
from .commands.solve import solve_command
from .commands.stream import stream_command
from .shell_state import ShellState


class Shell:
    """Interactive CLI shell for dialog with Quantalogic agents."""
    def __init__(self, agent_config: Optional[AgentConfig] = None):
        # Configure logger to INFO by default, clearing all existing handlers
        logger.remove()  # Remove all existing handlers to prevent DEBUG logs
        self.logger_sink_id = logger.add(sys.stderr, level="INFO")
        self.log_level = "INFO"
        
        # Initialize shell state
        self.state = ShellState(
            model_name="deepseek/deepseek-chat",
            max_iterations=10,
            streaming=True,
            mode="codeact"
        )
        
        # Initialize agents dictionary with a default agent
        default_config = agent_config or AgentConfig()
        default_agent = Agent(config=default_config)
        default_agent.add_observer(self._stream_token_observer, ["StreamToken"])
        self.agents: Dict[str, AgentState] = {
            "default": AgentState(
                agent=default_agent,
                model_name="deepseek/deepseek-chat",
                max_iterations=10
            )
        }
        self.current_agent_name: str = "default"
        
        # Initialize command registry
        self.command_registry = CommandRegistry()
        self._register_builtin_commands()
        self._load_plugin_commands()

    @property
    def current_agent(self) -> Agent:
        """Get the current agent."""
        return self.agents[self.current_agent_name].agent

    @property
    def current_message_history(self) -> List[Dict[str, str]]:
        """Get the current agent's message history."""
        return self.agents[self.current_agent_name].message_history

    def _register_builtin_commands(self) -> None:
        """Register all built-in commands with their arguments for autocompletion."""
        builtin_commands = [
            {"name": "help", "func": help_command, "help": "Show help for commands: /help [command]", "args": None},
            {"name": "chat", "func": chat_command, "help": "Chat with the agent: /chat <message>", "args": None},
            {"name": "solve", "func": solve_command, "help": "Solve a task: /solve <task>", "args": None},
            {"name": "exit", "func": exit_command, "help": "Exit the shell: /exit", "args": []},
            {"name": "history", "func": history_command, "help": "Show conversation history: /history", "args": []},
            {"name": "clear", "func": clear_command, "help": "Clear conversation history: /clear", "args": []},
            {"name": "stream", "func": stream_command, "help": "Toggle streaming: /stream on|off", "args": ["on", "off"]},
            {"name": "mode", "func": mode_command, "help": "Set or show the current mode: /mode [react|codeact]", "args": ["react", "codeact"]},
            {"name": "loglevel", "func": loglevel_command, "help": "Set or show the log level: /loglevel [DEBUG|INFO|WARNING|ERROR|CRITICAL]", "args": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]},
        ]
        for cmd in builtin_commands:
            self.command_registry.register(
                cmd["name"],
                lambda args, f=cmd["func"]: f(self, args),
                cmd["help"],
                cmd["args"]
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
                    print(f"Failed to load plugin command {ep.name}: {e}")
        except Exception as e:
            print(f"Error retrieving shell command entry points: {e}")

    async def _stream_token_observer(self, event: object) -> None:
        """Observer for streaming tokens (placeholder, handled in commands)."""
        pass  # No direct printing; let chat_command and solve_command handle display

    def bottom_toolbar(self) -> str:
        """Render a bottom toolbar with mode and agent information."""
        return f"Mode: {self.state.mode} | Agent: {self.current_agent.name or 'Default'}"

    async def run(self) -> None:
        """Run the interactive shell loop."""
        console = Console()
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
            message=lambda: f"[{self.current_agent.name or 'Agent'} | {self.state.mode}]> ",
            completer=completer,
            multiline=False,  # Single-line input, Ctrl+J for newlines
            history=FileHistory(str(history_file)),
            key_bindings=kb,
            bottom_toolbar=self.bottom_toolbar
        )

        # Welcome message with rich formatting
        welcome_message = (
            f"Welcome to Quantalogic Shell.\n\n"
            f"Interacting with agent: {self.current_agent.name or 'Agent'}\n"
            f"Mode: {self.state.mode} - plain messages are "
            f"{'tasks to solve' if self.state.mode == 'codeact' else 'chat messages'}.\n\n"
            f"Type /help for commands. Press Enter to send, Ctrl+J for new lines."
        )
        console.print(Panel(welcome_message, title="Quantalogic Shell", border_style="blue"))

        while True:
            try:
                user_input = await session.prompt_async()
                user_input = user_input.strip()
                if not user_input:
                    continue

                if user_input.startswith('/'):
                    command_input = user_input[1:].strip()
                    if not command_input:
                        console.print("[red]Error: No command provided. Try /help.[/red]")
                        continue
                    parts = command_input.split(maxsplit=1)
                    command_name = parts[0]
                    args = [parts[1]] if len(parts) > 1 else []
                    if command_name in self.command_registry.commands:
                        result = await self.command_registry.commands[command_name]["func"](args)
                        if result and command_name not in ["chat", "solve"]:
                            title = "Conversation History" if command_name == "history" else f"{command_name.capitalize()} Command"
                            console.print(Panel(result, title=title, border_style="blue"))
                    else:
                        console.print(f"[red]Unknown command: /{command_name}. Try /help.[/red]")
                else:
                    # Handle non-command input based on mode
                    if self.state.mode == "codeact":
                        await solve_command(self, [user_input])
                    else:  # react mode
                        await chat_command(self, [user_input])

            except KeyboardInterrupt:
                console.print("\nUse '/exit' to quit the shell.")
            except SystemExit:
                console.print("Goodbye!")
                break
            except Exception as e:
                logger.debug(f"Error: {e}")