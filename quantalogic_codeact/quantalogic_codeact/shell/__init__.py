"""
Quantalogic Shell module - CLI system integrated with the Quantalogic CodeAct agent.

Exposes the main Shell class and command registry functionality.
"""

from .shell import CommandRegistry, Shell

__all__ = ['Shell', 'CommandRegistry']