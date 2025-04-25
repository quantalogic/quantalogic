"""Command-line interface entry point for Quantalogic Agent."""

import importlib
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console

from quantalogic_codeact.codeact.plugin_manager import PluginManager

app = typer.Typer(no_args_is_help=True)
console = Console()

# Initialize PluginManager at module level to avoid duplicate loading
plugin_manager = PluginManager()
plugin_manager.load_plugins()  # This is now synchronous

# Dynamically load CLI commands from cli_commands directory
cli_commands_dir = Path(__file__).parent / "cli_commands"
for file in cli_commands_dir.glob("*.py"):
    if file.stem != "__init__":
        module_name = f"quantalogic_codeact.cli_commands.{file.stem}"
        try:
            module = importlib.import_module(module_name)
            command_name = file.stem.replace("_", "-")
            # Handle Typer app instances (e.g., list_toolboxes.py)
            if hasattr(module, "app") and isinstance(module.app, typer.Typer):
                if len(module.app.registered_commands) == 1:
                    # If there's exactly one command, register it directly
                    command = module.app.registered_commands[0]
                    app.command(name=command_name)(command.callback)
                    logger.debug(f"Loaded direct command: {command_name}")
                else:
                    # Otherwise, treat it as a subcommand group
                    app.add_typer(module.app, name=command_name)
                    logger.debug(f"Loaded command group: {command_name}")
            # Handle direct function commands (e.g., task.py)
            elif hasattr(module, file.stem) and callable(getattr(module, file.stem)):
                app.command(name=command_name)(getattr(module, file.stem))
                logger.debug(f"Loaded direct command: {command_name}")
        except ImportError as e:
            logger.error(f"Failed to load command module {module_name}: {e}")

# Load plugin CLI commands dynamically using the module-level plugin_manager
for cmd_name, cmd_func in plugin_manager.cli_commands.items():
    app.command(name=cmd_name)(cmd_func)

if __name__ == "__main__":
    app()