"""
Quantalogic Shell module - CLI system integrated with the Quantalogic CodeAct agent.

Exposes the main Shell class and command registry functionality.
"""

from . import __main__
from .shell import CommandRegistry, Shell


def main():
    """Run the shell from package entry point."""
    __main__.main()

__all__ = ['Shell', 'CommandRegistry', 'main']
