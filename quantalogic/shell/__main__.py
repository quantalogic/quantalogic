"""Main entry point for quantalogic.shell module execution."""

import asyncio
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import NestedCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from rich.console import Console

from .shell import Shell

def main():
    """Run the shell from package entry point."""
    shell = Shell()
    asyncio.run(shell.run())

if __name__ == "__main__":
    main()