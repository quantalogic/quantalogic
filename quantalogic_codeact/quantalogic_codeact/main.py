import asyncio
import importlib
import sys
from pathlib import Path
from typing import Optional

import typer
from loguru import logger

# Default logger configuration: only show ERROR and above until overridden by --loglevel
logger.remove()
logger.add(sys.stderr, level="ERROR", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")

import quantalogic_codeact.cli_commands.config_manager as cm  # noqa: E402
from quantalogic_codeact.codeact.agent_config import AgentConfig  # Import AgentConfig  # noqa: E402
from quantalogic_codeact.shell.shell import Shell  # noqa: E402

app = typer.Typer()

@app.callback(invoke_without_command=True)
def configure(
    ctx: typer.Context,
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to the configuration file to use"
    ),
    log_level: Optional[str] = typer.Option(
        None, "--loglevel", "-l", help="Override the log level: DEBUG|INFO|WARNING|ERROR|CRITICAL"
    ),
):
    """Set custom config path for all commands."""
    # Load or initialize AgentConfig
    if config:
        agent_config = AgentConfig.load_from_file(config)
    else:
        # Use the global config path when no explicit config is provided
        agent_config = AgentConfig.load_from_file(cm.GLOBAL_CONFIG_PATH)
        # Ensure required fields are initialized
        if hasattr(cm, 'ensure_config_initialized'):
            agent_config = cm.ensure_config_initialized(agent_config)
    
    ctx.obj = {"agent_config": agent_config, "log_level": log_level}
    # Configure logger based on config and CLI override
    level = log_level.upper() if log_level else agent_config.log_level.upper() if hasattr(agent_config, 'log_level') else cm.GLOBAL_DEFAULTS["log_level"].upper()
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    # Launch interactive shell if no subcommand was provided
    if ctx.invoked_subcommand is None:
        shell_instance = Shell(agent_config=agent_config, cli_log_level=log_level)
        asyncio.run(shell_instance.run())
        raise typer.Exit()

@app.command()
def shell(ctx: typer.Context):
    """Start the interactive shell."""
    log_level = ctx.obj.get("log_level")
    agent_config = ctx.obj["agent_config"]
    shell_instance = Shell(agent_config=agent_config, cli_log_level=log_level)
    asyncio.run(shell_instance.run())

# Dynamically load CLI commands from cli_commands/
cli_commands_dir = Path(__file__).parent / "cli_commands"
for file in cli_commands_dir.glob("*.py"):
    if file.stem != "__init__":
        module_name = f"quantalogic_codeact.cli_commands.{file.stem}"
        try:
            module = importlib.import_module(module_name)
            # Handle direct command functions (e.g., task.py)
            if hasattr(module, file.stem) and callable(getattr(module, file.stem)):
                command_name = file.stem.replace("_", "-")
                app.command(name=command_name)(getattr(module, file.stem))
            # Handle Typer subcommand groups (e.g., list_toolboxes.py)
            elif hasattr(module, "app") and isinstance(module.app, typer.Typer):
                app.add_typer(module.app, name=file.stem.replace("_", "-"))
        except ImportError as e:
            print(f"Failed to load command module {module_name}: {e}")

def main():
    """Main entry point: dispatch to Typer app (shell if no subcommand)."""
    app()

if __name__ == "__main__":
    main()