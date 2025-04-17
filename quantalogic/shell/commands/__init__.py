"""Shell commands package."""

# Import all commands here to make them available
from .chat import chat_command
from .clear import clear_command
from .exit import exit_command
from .help import help_command
from .history import history_command
from .mode import mode_command
from .solve import solve_command
from .stream import stream_command

__all__ = [
    'help_command',
    'chat_command',
    'solve_command',
    'exit_command',
    'history_command',
    'clear_command',
    'stream_command',
    'mode_command'
]