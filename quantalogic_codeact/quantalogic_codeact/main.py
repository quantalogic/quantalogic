import asyncio
import importlib
import sys
from pathlib import Path

import typer

from quantalogic_codeact.shell.shell import Shell

app = typer.Typer()

@app.command()
def shell():
    """Start the interactive shell."""
    shell_instance = Shell()
    asyncio.run(shell_instance.run())

# Dynamically load CLI commands from codeact/cli_commands/
cli_commands_dir = Path(__file__).parent / "codeact" / "cli_commands"
for file in cli_commands_dir.glob("*.py"):
    if file.stem != "__init__":
        module_name = f"quantalogic_codeact.codeact.cli_commands.{file.stem}"
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
    """Main entry point: default to shell mode if no arguments, otherwise run CLI."""
    if len(sys.argv) == 1:
        # No subcommand provided: run shell
        shell()
    else:
        # Run typer app for CLI commands
        app()

if __name__ == "__main__":
    main()