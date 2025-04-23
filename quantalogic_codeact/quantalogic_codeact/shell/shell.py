import sys
from dataclasses import fields  # for filtering config keys
from difflib import get_close_matches  # Added for command suggestions
from importlib.metadata import entry_points
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import NestedCompleter
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

import quantalogic_codeact.codeact.cli_commands.config_manager as config_manager
from quantalogic_codeact.codeact.agent import Agent, AgentConfig
from quantalogic_codeact.codeact.commands.toolbox.get_tool_doc import get_tool_doc
from quantalogic_codeact.codeact.commands.toolbox.install_toolbox import install_toolbox
from quantalogic_codeact.codeact.commands.toolbox.list_toolbox_tools import list_toolbox_tools
from quantalogic_codeact.codeact.commands.toolbox.uninstall_toolbox import uninstall_toolbox
from quantalogic_codeact.codeact.conversation_manager import ConversationManager
from quantalogic_codeact.version import get_version

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
from .commands.edit import edit_command
from .commands.exit import exit_command
from .commands.help import help_command
from .commands.history import history_command
from .commands.inputmode import inputmode_command
from .commands.list_models import listmodels_command
from .commands.load import load_command
from .commands.loglevel import loglevel_command
from .commands.mode import mode_command
from .commands.save import save_command
from .commands.set import set_command
from .commands.set_temperature import set_temperature_command  # Added import
from .commands.setmodel import setmodel_command
from .commands.solve import solve_command
from .commands.stream import stream_command
from .commands.tutorial import tutorial_command
from .commands.version import version_command
from .shell_state import ShellState

console = Console()

class Shell:
    """Interactive CLI shell for dialog with Quantalogic agents."""
    def __init__(self, agent_config: Optional[AgentConfig] = None, cli_log_level: Optional[str] = None):
        # Configure logger based on config file (default ERROR)
        cfg = config_manager.load_global_config()
        if cli_log_level:
            level = cli_log_level.upper()
        else:
            level = cfg.get("log_level", config_manager.GLOBAL_DEFAULTS.get("log_level", "ERROR")).upper()
        logger.remove()
        self.logger_sink_id = logger.add(
            sys.stderr,
            level=level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
                   "<cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
        )
        self.log_level = level
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
        
        # Initialize conversation manager
        self.conversation_manager = ConversationManager()
        
        # Load or initialize global config
        if not config_manager.GLOBAL_CONFIG_PATH.exists():
            default_data = {
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
                "agent_tool_timeout": 30,
                "temperature": 0.7,  # Added default temperature
                "installed_toolboxes": [],
                "log_level": config_manager.GLOBAL_DEFAULTS.get("log_level", "ERROR")
            }
            config_manager.save_global_config(default_data)
            logger.info(f"Created global configuration at {config_manager.GLOBAL_CONFIG_PATH}")
            config_data = default_data
        else:
            config_data = config_manager.load_global_config()
        # Prepare AgentConfig args
        config_data.pop("log_level", None)
        try:
            # Filter out unsupported keys based on AgentConfig schema
            valid_keys = {f.name for f in fields(AgentConfig)}
            for key in list(config_data):
                if key not in valid_keys:
                    logger.warning(f"Unknown config key '{key}' ignored.")
                    config_data.pop(key)
            default_config = AgentConfig(**config_data)
            logger.info(f"Loaded configuration from {config_manager.GLOBAL_CONFIG_PATH}")
        except Exception as e:
            logger.error(f"Failed to initialize AgentConfig: {e}. Using minimal configuration.")
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
        # Convert Message objects to dicts for compatibility with history_command
        return [
            {"role": msg.role, "content": msg.content, "nanoid": msg.nanoid}
            for msg in self.conversation_manager.get_history()
        ]

    def _register_builtin_commands(self) -> None:
        """Register all built-in commands with their arguments for autocompletion."""
        builtin_commands = [
            {"name": "help", "func": help_command, "help": "Show help for commands: /help [command]", "args": None},
            {"name": "chat", "func": chat_command, "help": "Chat with the agent: /chat <message>", "args": None},
            {"name": "solve", "func": solve_command, "help": "Solve a task: /solve <task>", "args": None},
            {"name": "compose", "func": compose_command, "help": "Compose input in external editor: /compose", "args": []},
            {"name": "edit", "func": edit_command, "help": "Edit last user message: /edit", "args": []},
            {"name": "exit", "func": exit_command, "help": "Exit the shell: /exit", "args": []},
            {"name": "history", "func": history_command, "help": "Show conversation history: /history [n]", "args": None},
            {"name": "clear", "func": clear_command, "help": "Clear conversation history: /clear", "args": []},
            {"name": "stream", "func": stream_command, "help": "Toggle streaming: /stream on|off", "args": ["on", "off"]},
            {"name": "mode", "func": mode_command, "help": "Set or show mode: /mode [chat|codeact]", "args": ["chat", "codeact"]},
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
            {"name": "set temperature", "func": set_temperature_command, "help": "Set or show temperature: /set temperature <value>", "args": None},
            {"name": "config show", "func": config_show, "help": "Show the current configuration", "args": []},
            {"name": "config save", "func": config_save, "help": "Save the current configuration to a file: /config save <filename>", "args": None},
            {"name": "config load", "func": config_load, "help": "Load a configuration from a file: /config load <filename>", "args": None},
            {"name": "toolbox install", "func": install_toolbox, "help": "Install a toolbox: /toolbox install <toolbox_name>", "args": None},
            {"name": "toolbox uninstall", "func": uninstall_toolbox, "help": "Uninstall a toolbox: /toolbox uninstall <toolbox_name>", "args": None},
            {"name": "toolbox tools", "func": list_toolbox_tools, "help": "List tools in a toolbox: /toolbox tools <toolbox_name>", "args": None},
            {"name": "toolbox doc", "func": get_tool_doc, "help": "Show tool documentation: /toolbox doc <toolbox_name> <tool_name>", "args": None},
            {"name": "listmodels", "func": listmodels_command, "help": "List models using LLM util: /listmodels", "args": []},
            {"name": "version", "func": version_command, "help": "Show package version: /version", "args": []},
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
        """Render a bottom toolbar with mode, agent, model, temperature, and version information as prompt_toolkit HTML."""
        # Retrieve the current temperature from the agent's react_agent
        temperature = self.current_agent.react_agent.temperature
        
        if self.high_contrast:
            # High-contrast mode: single style with all info
            return HTML(
                f'<b><style fg="ansiblack" bg="#E6E6FA">'
                f'Mode: {self.state.mode} | '
                f'Agent: {self.current_agent.name or "Default"} | '
                f'Model: {self.current_agent.model} | '
                f'Temperature: {temperature:.2f} | '
                f'Version: {get_version()}'
                f'</style></b>'
            )
        else:
            # Default mode: multi-colored sections
            return HTML(
                f'<b>'
                f'<style fg="ansiwhite" bg="ansired"> Mode: {self.state.mode} </style>'
                f'<style fg="ansiwhite" bg="ansigreen"> Agent: {self.current_agent.name or "Default"} </style>'
                f'<style fg="ansiwhite" bg="ansiblue"> Model: {self.current_agent.model} </style>'
                f'<style fg="ansiwhite" bg="ansiyellow"> Temperature: {temperature:.2f} </style>'
                f'<style fg="ansiwhite" bg="ansimagenta"> Version: {get_version()} </style>'
                f'</b>'
            )

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
            message=lambda: HTML(
                f'<ansigreen>[cfg:{config_manager.GLOBAL_CONFIG_PATH.name}]</ansigreen> '
                f'<ansicyan>[{self.current_agent.name or "Agent"}]</ansicyan> '
                f'<ansiyellow>[{self.state.mode}]></ansiyellow> '
            ),
            completer=completer,
            multiline=self.multiline,
            history=FileHistory(str(history_file)),
            key_bindings=kb,
            bottom_toolbar=self.bottom_toolbar
        )
        self.session = session  # Store for inputmode updates

        # Welcome message
        welcome_message = (
            f"Welcome to Quantalogic Shell (v{get_version()}).\n\n"
            f"Interacting with agent: {self.current_agent.name or 'Agent'}\n"
            f"Mode: {self.state.mode} - plain messages are "
            f"{'tasks to solve' if self.state.mode == 'codeact' else 'chat messages'}.\n\n"
            f"Type /help for commands. Press Enter to send, Ctrl+J for new lines."
        )
        console.print(Panel(welcome_message, title="Quantalogic Shell", border_style="blue"))

        while True:
            try:
                # Use default parameter to prefill edited text if queued
                if hasattr(self, 'next_input_text'):
                    default = self.next_input_text
                    delattr(self, 'next_input_text')
                    user_input = await session.prompt_async(default=default)
                else:
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
                        border_style = "bright_red" if self.high_contrast else "red"
                        console.print(Panel("No command provided. Try /help.", title="Error", border_style=border_style))
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
                            # Use Markdown rendering for toolbox commands
                            border_color = "bright_blue" if self.high_contrast else "blue"
                            if matched_command in ["toolbox doc", "toolbox tools"]:
                                console.print(Markdown(result))
                            else:
                                title = "Conversation History" if matched_command == "history" else f"{matched_command.capitalize()} Command"
                                console.print(Panel(result, title=title, border_style=border_color))
                    else:
                        similar = get_close_matches(command_input, self.command_registry.commands.keys(), n=1, cutoff=0.6)
                        if similar:
                            suggestion = f"Did you mean '/{similar[0]}'?"
                        else:
                            suggestion = ""
                        error_message = f"Unknown command: /{command_input}. {suggestion} Try /help."
                        border_style = "bright_red" if self.high_contrast else "red"
                        console.print(Panel(error_message, title="Error", border_style=border_style))
                else:
                    # Handle non-command input based on mode
                    if self.state.mode == "codeact":
                        await solve_command(self, [user_input])
                    else:  # chat mode
                        await chat_command(self, [user_input])

            except KeyboardInterrupt:
                console.print(Panel("Goodbye!", title="Exit", border_style="green"))
                break
            except SystemExit:
                console.print(Panel("Goodbye!", title="Exit", border_style="green"))
                break
            except Exception as e:
                if self.debug:
                    logger.exception(f"Error processing input: {user_input}")
                error_message = f"Error: {e}. Try /help for assistance."
                border_style = "bright_red" if self.high_contrast else "red"
                console.print(Panel(error_message, title="Error", border_style=border_style))