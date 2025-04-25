import sys
from difflib import get_close_matches
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

import quantalogic_codeact.cli_commands.config_manager as config_manager
from quantalogic_codeact.codeact.agent import Agent
from quantalogic_codeact.codeact.agent_config import GLOBAL_CONFIG_PATH, GLOBAL_DEFAULTS, AgentConfig
from quantalogic_codeact.codeact.conversation_manager import ConversationManager
from quantalogic_codeact.codeact.events import ToolConfirmationRequestEvent
from quantalogic_codeact.commands.toolbox.disable_toolbox import disable_toolbox
from quantalogic_codeact.commands.toolbox.enable_toolbox import enable_toolbox
from quantalogic_codeact.commands.toolbox.get_tool_doc import get_tool_doc
from quantalogic_codeact.commands.toolbox.install_toolbox import install_toolbox
from quantalogic_codeact.commands.toolbox.installed_toolbox import installed_toolbox
from quantalogic_codeact.commands.toolbox.list_toolbox_tools import list_toolbox_tools
from quantalogic_codeact.commands.toolbox.uninstall_toolbox import uninstall_toolbox
from quantalogic_codeact.version import get_version

from .agent_state import AgentState
from .banner import get_welcome_message, print_welcome_banner
from .command_registry import CommandRegistry
from .commands.agent import agent_command
from .commands.chat import chat_command
from .commands.clear import clear_command
from .commands.compose import compose_command
from .commands.config_load import config_load
from .commands.config_save import config_save
from .commands.config_show import config_show
from .commands.contrast import contrast_command
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
from .commands.set_temperature import set_temperature_command
from .commands.setmodel import setmodel_command
from .commands.solve import solve_command
from .commands.stream import stream_command
from .commands.tutorial import tutorial_command
from .commands.version import version_command

console = Console()

class Shell:
    """Interactive CLI shell for dialog with Quantalogic agents."""
    def __init__(self, agent_config: Optional[AgentConfig] = None, cli_log_level: Optional[str] = None):
        # Configure logger based on config file (default ERROR)
        self.agent_config = agent_config or AgentConfig.load_from_file(GLOBAL_CONFIG_PATH)
        # Ensure config is properly initialized with required fields
        if hasattr(config_manager, 'ensure_config_initialized'):
            self.agent_config = config_manager.ensure_config_initialized(self.agent_config)
            
        # Create default config file if it doesn't exist
        config_path = Path(GLOBAL_CONFIG_PATH)
        if not config_path.exists():
            try:
                logger.info(f"Creating default configuration file at {config_path}")
                self.agent_config.save_to_file(str(config_path))
            except Exception as e:
                logger.error(f"Failed to create default config file: {e}")
        if cli_log_level:
            level = cli_log_level.upper()
        else:
            level = self.agent_config.log_level.upper() if hasattr(self.agent_config, 'log_level') else GLOBAL_DEFAULTS.get("log_level", "ERROR").upper()
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
        
        # Initialize conversation manager
        self.conversation_manager = ConversationManager()
        
        # Debug log for enabled_toolboxes value before agent initialization
        logger.debug(f"Shell initializing agent with enabled_toolboxes: {self.agent_config.enabled_toolboxes}")
    
        # Initialize the default agent with the loaded config
        default_agent = Agent(config=self.agent_config)
        default_agent.add_observer(self._stream_token_observer, ["StreamToken"])
        # Subscribe to tool confirmation events - this is critical for proper confirmation handling
        default_agent.add_observer(self._handle_tool_confirmation, ["ToolConfirmationRequest"])
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
            {"name": "edit", "func": edit_command, "help": "Edit a previous user message: /edit [INDEX_OR_ID]", "args": []},
            {"name": "exit", "func": exit_command, "help": "Exit the shell: /exit", "args": []},
            {"name": "history", "func": history_command, "help": "Show conversation history: /history [n]", "args": None},
            {"name": "clear", "func": clear_command, "help": "Clear conversation history: /clear", "args": []},
            {"name": "stream", "func": stream_command, "help": "Toggle streaming: /stream on|off", "args": ["on", "off"]},
            {"name": "mode", "func": mode_command, "help": "Set or show mode: /mode [chat|codeact]", "args": ["chat", "codeact"]},
            {"name": "loglevel", "func": loglevel_command, "help": "Set log level: /loglevel [DEBUG|INFO|WARNING|ERROR|CRITICAL]", "args": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]},
            {"name": "save", "func": save_command, "help": "Save history: /save <filename>", "args": None},
            {"name": "load", "func": load_command, "help": "Load history: /load <filename>", "args": None},
            {"name": "agent", "func": agent_command, "help": "Switch agent: /agent <name>", "args": list(self.agents.keys())},
            {"name": "tutorial", "func": tutorial_command, "help": "Show tutorial: /tutorial", "args": []},
            {"name": "inputmode", "func": inputmode_command, "help": "Set input mode: /inputmode single|multi", "args": ["single", "multi"]},
            {"name": "contrast", "func": contrast_command, "help": "Toggle high-contrast mode: /contrast on|off", "args": ["on", "off"]},
            {"name": "setmodel", "func": setmodel_command, "help": "Set model and switch to a new agent: /setmodel <model_name>", "args": None},
            {"name": "set", "func": set_command, "help": "Set a config field: /set <field> <value>", "args": None},
            {"name": "set temperature", "func": set_temperature_command, "help": "Set or show temperature: /set temperature <value>", "args": None},
            {"name": "config", "func": config_show, "help": "Show the current configuration", "args": []},
            {"name": "config show", "func": config_show, "help": "Show the current configuration", "args": []},
            {"name": "config save", "func": config_save, "help": "Save the current configuration to a file: /config save <filename>", "args": None},
            {"name": "config load", "func": config_load, "help": "Load a configuration from a file: /config load <filename>", "args": None},
            {"name": "toolbox", "func": list_toolbox_tools, "help": "List tools in enabled toolboxes: /toolbox [<toolbox_name>]", "args": None},
            {"name": "toolbox install", "func": install_toolbox, "help": "Install a toolbox: /toolbox install <toolbox_name>", "args": None},
            {"name": "toolbox uninstall", "func": uninstall_toolbox, "help": "Uninstall a toolbox: /toolbox uninstall <toolbox_name>", "args": None},
            {"name": "toolbox installed", "func": installed_toolbox, "help": "Show installed toolboxes: /toolbox installed", "args": None},
            {"name": "toolbox enable", "func": enable_toolbox, "help": "Enable a toolbox: /toolbox enable <toolbox_name>", "args": None},
            {"name": "toolbox disable", "func": disable_toolbox, "help": "Disable a toolbox: /toolbox disable <toolbox_name>", "args": None},
            {"name": "toolbox tools", "func": list_toolbox_tools, "help": "List tools in a toolbox: /toolbox tools <toolbox_name>", "args": None},
            {"name": "toolbox doc", "func": get_tool_doc, "help": "Show tool documentation: /toolbox doc <toolbox_name> <tool_name>", "args": None},
            {"name": "listmodels", "func": listmodels_command, "help": "List models using LLM util: /listmodels", "args": []},
            {"name": "version", "func": version_command, "help": "Show package version: /version", "args": []},
            {"name": "banner", "func": self.banner_command, "help": "Display the welcome banner again", "args": []},
        ]
        for cmd in builtin_commands:
            if cmd["name"] == "banner":
                # Directly use the bound method for banner
                self.command_registry.register(
                    cmd["name"],
                    lambda args=None: cmd["func"](args or []),
                    cmd["help"],
                    cmd["args"]
                )
            else:
                # Standard registration for other commands
                self.command_registry.register(
                    cmd["name"],
                    lambda args, f=cmd["func"], s=self: f(s, args),
                    cmd["help"],
                    cmd["args"]
                )
        # Set args for /help to include all command names for autocompletion
        self.command_registry.commands["help"]["args"] = list(self.command_registry.commands.keys())

    async def banner_command(self, args: List[str]) -> None:
        """Display the welcome banner with consistent colors."""
        agent_name = getattr(self.agent_config, 'agent_name', 'QUANTA') or 'QUANTA'
        print_welcome_banner(
            agent_name,
            self.agent_config.mode,
            self.high_contrast
        )

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
        
    async def _handle_tool_confirmation(self, event: ToolConfirmationRequestEvent) -> None:
        """Handle tool confirmation requests by interacting with the user.
        
        This method is called when a tool requires confirmation before execution.
        It displays a prompt to the user and sets the confirmation result on the event's future.
        """
        if event.event_type != "ToolConfirmationRequest":
            return
        
        # Add debug logging    
        logger.debug(f"Received tool confirmation request for: {event.tool_name}")
        logger.debug(f"Confirmation message: {event.confirmation_message}")
            
        # Format parameter display nicely
        formatted_params = '\n'.join(f"  - {k}: {v}" for k, v in event.parameters_summary.items())
        
        # Display confirmation panel with message and parameters
        panel = Panel(
            f"Tool: {event.tool_name}\n\nParameters:\n{formatted_params}\n\n{event.confirmation_message}",
            title="Confirmation Required", 
            border_style="yellow"
        )
        console.print(panel)
        console.print("[bold yellow]Type [bold white]'yes'[/bold white] or [bold white]'no'[/bold white] to confirm or cancel this operation.[/bold yellow]")
        
        # Log that we're waiting for confirmation
        logger.debug("Shell is now getting confirmation input directly")
        
        # DIRECT HANDLING: Get and process input directly
        try:
            # Use direct Python input() instead of prompt_toolkit
            response = input("Confirm (yes/no): ").strip().lower()
            console.print(f"[italic]Received response: '{response}'[/italic]")
            
            # Process the response directly
            if response not in ['yes', 'no']:
                console.print("[bold red]Invalid response. Please enter exactly 'yes' or 'no'.[/bold red]")
                # Try again once more
                response = input("Confirm (yes/no): ").strip().lower()
                if response not in ['yes', 'no']:
                    console.print("[bold red]Invalid response again. Treating as 'no'.[/bold red]")
                    response = 'no'
            
            # Process confirmation
            confirmed = (response == 'yes')
            logger.debug(f"Confirmation response: {confirmed}")
            
            # Set the result on the event's future
            if event.confirmation_future and not event.confirmation_future.done():
                event.confirmation_future.set_result(confirmed)
                logger.debug("Successfully set confirmation result on future")
                
                # Show result to user with clearer feedback
                if confirmed:
                    console.print("[bold green]Confirmation accepted - proceeding with operation[/bold green]")
                else:
                    console.print("[bold red]Confirmation declined - ENTIRE TASK ABORTED[/bold red]")
                    console.print("[italic]The entire task execution has been stopped because you answered 'no'[/italic]")
                    console.print("[dim]This is the behavior you requested - to stop the solve task on confirmation decline[/dim]")
            else:
                logger.error("No valid confirmation future found in event or future already done")
                console.print("[bold orange3]Confirmation response not processed - no valid response mechanism found.[/bold orange3]")
        except Exception as e:
            logger.error(f"Error getting confirmation input: {e}")
            console.print(f"[bold red]Error getting confirmation input: {e}[/bold red]")
            # Set the future to False if it exists and is not done
            if event.confirmation_future and not event.confirmation_future.done():
                event.confirmation_future.set_result(False)

    def bottom_toolbar(self):
        """Render a bottom toolbar with mode, agent, model, temperature, and version information as prompt_toolkit HTML."""
        # Retrieve the current temperature from the agent's react_agent
        temperature = self.current_agent.react_agent.temperature
        
        if self.high_contrast:
            # High-contrast mode: single style with all info
            return HTML(
                f'<b><style fg="ansiblack" bg="#E6E6FA">'
                f'Mode: {self.agent_config.mode} | '
                f'Agent: {self.current_agent.name or "Default"} | '
                f'Model: {self.current_agent.model} | '
                f'MaxIter: {self.agent_config.max_iterations} | '
                f'Temperature: {temperature:.2f} | '
                f'Version: {get_version()}'
                f'</style></b>'
            )
        else:
            # Default mode: multi-colored sections
            return HTML(
                f'<b>'
                f'<style fg="ansiwhite" bg="ansired"> Mode: {self.agent_config.mode} </style>'
                f'<style fg="ansiwhite" bg="ansigreen"> Agent: {self.current_agent.name or "Default"} </style>'
                f'<style fg="ansiwhite" bg="ansiblue"> Model: {self.current_agent.model} </style>'
                f'<style fg="ansiwhite" bg="ansicyan"> MaxIter: {self.agent_config.max_iterations} </style>'
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
                f'<ansigreen>[cfg:{GLOBAL_CONFIG_PATH.name}]</ansigreen> '
                f'<ansicyan>[{self.current_agent.name or "Agent"}]</ansicyan> '
                f'<ansiyellow>[{self.agent_config.mode}]></ansiyellow> '
            ),
            completer=completer,
            multiline=self.multiline,
            history=FileHistory(str(history_file)),
            key_bindings=kb,
            bottom_toolbar=self.bottom_toolbar
        )
        self.session = session  # Store for inputmode updates

        # Welcome message
        welcome_message = get_welcome_message(self.current_agent.name, self.agent_config.mode)
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
                            if matched_command in ["toolbox doc", "toolbox tools", "toolbox"]:
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
                    if self.agent_config.mode == "codeact":
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