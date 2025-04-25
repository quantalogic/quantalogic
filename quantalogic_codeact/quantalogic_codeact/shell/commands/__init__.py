"""Shell commands package."""

from .chat import chat_command  # noqa: I001
from .clear import clear_command
from .compose import compose_command
from .exit import exit_command
from .help import help_command
from .history import history_command
from .loglevel import loglevel_command
from .mode import mode_command
from .solve import solve_command
from .stream import stream_command
from .save import save_command
from .load import load_command
from .agent import agent_command
from .tutorial import tutorial_command
from .inputmode import inputmode_command
from .contrast import contrast_command
from .setmodel import setmodel_command
from .set_temperature import set_temperature_command  # Added import
from .config_show import config_show
from .config_save import config_save
from .config_load import config_load
from quantalogic_codeact.commands.toolbox.install_toolbox import install_toolbox
from quantalogic_codeact.commands.toolbox.uninstall_toolbox import uninstall_toolbox
from quantalogic_codeact.commands.toolbox.list_toolbox_tools import list_toolbox_tools
from quantalogic_codeact.commands.toolbox.get_tool_doc import get_tool_doc

__all__ = [
    'help_command',
    'chat_command',
    'compose_command',
    'solve_command',
    'exit_command',
    'history_command',
    'clear_command',
    'stream_command',
    'mode_command',
    'loglevel_command',
    'save_command',
    'load_command',
    'agent_command',
    'tutorial_command',
    'inputmode_command',
    'contrast_command',
    'setmodel_command',
    'set_temperature_command',  # Added to __all__
    'config_show',
    'config_save',
    'config_load',
    'install_toolbox',
    'uninstall_toolbox',
    'list_toolbox_tools',
    'get_tool_doc',
]