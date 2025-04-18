import sys
from importlib.metadata import entry_points
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from loguru import logger
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import NestedCompleter
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from rich.console import Console
from rich.panel import Panel

from ..codeact.agent import Agent, AgentConfig
from .agent_state import AgentState
from .command_registry import CommandRegistry
from .commands.agent import agent_command
from .commands.chat import chat_command
from .commands.clear import clear_command
from .commands.compose import compose_command
from .commands.config_load import config_load
from .commands.config_save import config_save
from .commands.config_show import config_show
from .commands.contrast import contrast_command
from .commands.debug import debug_command
from .commands.exit import exit_command
from .commands.help import help_command
from .commands.history import history_command
from .commands.inputmode import inputmode_command
from .commands.load import load_command
from .commands.loglevel import loglevel_command
from .commands.mode import mode_command
from .commands.save import save_command
from .commands.set import set_command
from .commands.setmodel import setmodel_command
from .commands.solve import solve_command
from .commands.stream import stream_command
from .commands.tutorial import tutorial_command
from .history_manager import HistoryManager
from .shell_state import ShellState

console = Console()

class Shell:
    """Interactive CLI shell for dialog with Quantalogic agents."""
    def __init__(self, agent_config: Optional[AgentConfig] = None):
        # Configure logger to INFO by default
        logger.remove()
        self.logger_sink_id = logger.add(sys.stderr, level="INFO")
        self.log_level = "INFO"
        self.debug = False  # For detailed error logging
        self.high_contrast = False  # For accessibility
        self.multiline = False  # Default to single-line input
        
        # Initialize shell state
        self.state = ShellState(
            model_name="deepseek/deepseek-chat",
            max_iterations=10,
            streaming=True,
            mode="codeact"
        )
        
        # Initialize history manager
        self.history_manager = HistoryManager()
        
        # Check for .quantalogic/config.yaml in the current working directory
        config_file_path = Path(".quantalogic/config.yaml").resolve()
        if not config_file_path.exists():
            default_config_data = {
                "model": "gemini/gemini-2.0-flash",
                "max_iterations": 5,
                "enabled_toolboxes": [],
                "reasoner": {"name": "default"},
                "executor": {"name": "default"},
                "personality": None,
                "backstory": None,
                "sop": None,
                "name": None,
                "tools_config": None,
                "profile": None,
                "customizations": None,
                "agent_tool_model": "gemini/gemini-2.0-flash",
                "agent_tool_timeout": 30
            }
            try:
                config_file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(config_file_path, "w") as f:
                    yaml.safe_dump(default_config_data, f, default_flow_style=False)
                logger.info(f"Created default configuration file at {config_file_path}")
                console.print(Panel(f"Created default configuration file at {config_file_path}", title="Info", border_style="green"))
            except Exception as e:
                logger.error(f"Failed to create default configuration file at {config_file_path}: {e}")
            try:
                default_config = AgentConfig(**default_config_data)
            except Exception as e:
                logger.error(f"Failed to initialize AgentConfig from default data: {e}. Using minimal configuration.")
                default_config = AgentConfig()
        else:
            try:
                with open(config_file_path) as f:
                    config_data = yaml.safe_load(f) or {}
                default_config = AgentConfig(**config_data)
                logger.info(f"Loaded configuration from {config_file_path}")
            except Exception as e:
                logger.error(f"Failed to load .quantalogic/config.yaml: {e}. Using minimal configuration.")
                default_config = AgentConfig()
        
        # Initialize the default agent with the loaded or default config
        default_agent = Agent(config=agent_config or default_config)
        default_agent.add_observer(self._stream_token_observer, ["StreamToken"])
        self.agents: Dict[str, AgentState] = {
            "default": AgentState(agent=default_agent)
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
        return self.history_manager.get_history()

    def _register_builtin_commands(self) -> None:
        """Register all built-in commands with their arguments for autocompletion."""
        builtin_commands = [
            {"name": "help", "func": help_command, "help": "Show help for commands: /help [command]", "args": None},
            {"name": "chat", "func": chat_command, "help": "Chat with the agent: /chat <message>", "args": None},
            {"name": "solve", "func": solve_command, "help": "Solve a task: /solve <task>", "args": None},
            {"name": "compose", "func": compose_command, "help": "Compose input in external editor: /compose", "args": []},
            {"name": "exit", "func": exit_command, "help": "Exit the shell: /exit", "args": []},
            {"name": "history", "func": history_command, "help": "Show conversation history: /history [n]", "args": None},
            {"name": "clear", "func": clear_command, "help": "Clear conversation history: /clear", "args": []},
            {"name": "stream", "func": stream_command, "help": "Toggle streaming: /stream on|off", "args": ["on", "off"]},
            {"name": "mode", "func": mode_command, "help": "Set or show mode: /mode [react|codeact]", "args": ["react", "codeact"]},
            {"name": "loglevel", "func": loglevel_command, "help": "Set log level: /loglevel [DEBUG|INFO|WARNING|ERROR|CRITICAL]", "args": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]},
            {"name": "debug", "func": debug_command, "help": "Toggle debug mode: /debug on|off", "args": ["on", "off"]},
            {"name": "save", "func": save_command, "help": "Save history: /save <filename>", "args": None},
            {"name": "load", "func": load_command, "help": "Load history: /load <filename>", "args": None},
            {"name": "agent", "func": agent_command, "help": "Switch agent: /agent <name>", "args": list(self.agents.keys())},
            {"name": "tutorial", "func": tutorial_command, "help": "Show tutorial: /tutorial", "args": []},
            {"name": "inputmode", "func": inputmode_command, "help": "Set input mode: /inputmode single|multi", "args": ["single", "multi"]},
            {"name": "contrast", "func": contrast_command, "help": "Toggle high-contrast mode: /contrast on|off", "args": ["on", "off"]},
            {"name": "setmodel", "func": setmodel_command, "help": "Set model and switch to a new agent: /setmodel <model_name>", "args": None},
            {"name": "set", "func": set_command, "help": "Set a config field: /set <field> <value>", "args": None},
            {"name": "config show", "func": config_show, "help": "Show the current configuration", "args": []},
            {"name": "config save", "func": config_save, "help": "Save the current configuration to a file: /config save <filename>", "args": None},
            {"name": "config load", "func": config_load, "help": "Load a configuration from a file: /config load <filename>", "args": None},
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
                    console.print(Panel(f"Failed to load plugin command {ep.name}: {e}", title="Error", border_style="red"))
        except Exception as e:
            console.print(Panel(f"Error retrieving command entry points: {e}", title="Error", border_style="red"))

    async def _stream_token_observer(self, event: object) -> None:
        """Observer for streaming tokens (handled in commands)."""
        pass

    def bottom_toolbar(self):
        """Render a bottom toolbar with mode, agent, and model information as prompt_toolkit HTML."""
        if self.high_contrast:
            return HTML(f'<b><ansiwhite>Mode: {self.state.mode} | Agent: {self.current_agent.name or "Default"} | Model: {self.current_agent.model}</ansiwhite></b>')
        else:
            return HTML(f'<b><ansiyellow>Mode: {self.state.mode} | Agent: {self.current_agent.name or "Default"} | Model: {self.current_agent.model}</ansiyellow></b>')

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
            message=lambda: f"[{self.current_agent.name or 'Agent'} | {self.state.mode}]> ",
            completer=completer,
            multiline=self.multiline,
            history=FileHistory(str(history_file)),
            key_bindings=kb,
            bottom_toolbar=self.bottom_toolbar
        )
        self.session = session  # Store for inputmode updates

        # Welcome message
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

                # Display user input with label and color
                color = "bright_blue" if self.high_contrast else "blue"
                console.print(f"[bold {color}]User:[/bold {color}] {user_input}")

                if user_input.startswith('/'):
                    command_input = user_input[1:].strip()
                    if not command_input:
                        console.print(Panel("No command provided. Try /help.", title="Error", border_style="red"))
                        continue

                    # Support multi-word commands by matching the longest command name first
                    matched_command = None
                    for name in sorted(self.command_registry.commands.keys(), key=lambda x: -len(x)):
                        if command_input == name or command_input.startswith(name + " "):
                            matched_command = name
                            remaining = command_input[len(name):].strip()
                            args = remaining.split() if remaining else []
                            break
                    if matched_command:
                        result = await self.command_registry.commands[matched_command]["func"](args)
                        if result and matched_command not in ["chat", "solve", "tutorial"]:
                            title = "Conversation History" if matched_command == "history" else f"{matched_command.capitalize()} Command"
                            border_color = "bright_blue" if self.high_contrast else "blue"
                            console.print(Panel(result, title=title, border_style=border_color))
                    else:
                        console.print(Panel(f"Unknown command: /{command_input}. Try /help.", title="Error", border_style="red"))
                else:
                    # Handle non-command input based on mode
                    if self.state.mode == "codeact":
                        await solve_command(self, [user_input])
                    else:  # react mode
                        await chat_command(self, [user_input])

            except KeyboardInterrupt:
                console.print(Panel("\nUse '/exit' to quit the shell.", title="Info", border_style="yellow"))
            except SystemExit:
                console.print(Panel("Goodbye!", title="Exit", border_style="green"))
                break
            except Exception as e:
                if self.debug:
                    logger.exception("Shell error")
                error_message = f"Error: {e}. Try /help for assistance."
                console.print(Panel(error_message, title="Error", border_style="red"))