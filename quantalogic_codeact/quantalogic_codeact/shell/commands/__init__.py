"""Shell commands package."""

from .chat import chat_command  # noqa: I001
from .clear import clear_command
from .exit import exit_command
from .help import help_command
from .history import history_command
from .loglevel import loglevel_command
from .mode import mode_command
from .solve import solve_command
from .stream import stream_command
from .debug import debug_command
from .save import save_command
from .load import load_command
from .agent import agent_command
from .tutorial import tutorial_command
from .inputmode import inputmode_command
from .contrast import contrast_command
from .setmodel import setmodel_command  # Added new command

__all__ = [
    'help_command',
    'chat_command',
    'solve_command',
    'exit_command',
    'history_command',
    'clear_command',
    'stream_command',
    'mode_command',
    'loglevel_command',
    'debug_command',
    'save_command',
    'load_command',
    'agent_command',
    'tutorial_command',
    'inputmode_command',
    'contrast_command',
    'setmodel_command',  # Added to export list
]