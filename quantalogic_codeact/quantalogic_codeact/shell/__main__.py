"""Main entry point for quantalogic.shell module execution."""

import asyncio

from .shell import Shell


def main():
    """Run the shell from package entry point."""
    shell = Shell()
    asyncio.run(shell.run())

if __name__ == "__main__":
    main()