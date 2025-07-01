"""QuantaLogic package initialization - Re-export from quantalogic_react."""

import warnings
from importlib.metadata import version as get_version

# Suppress specific warnings related to Pydantic's V2 configuration changes
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="pydantic.*",
    message=".*config keys have changed in V2:.*|.*'fields' config key is removed in V2.*",
)

try:
    __version__: str = get_version("quantalogic")
except Exception as e:
    __version__ = "unknown"
    print(f"Unable to retrieve version: {e}")

# Re-export public API from quantalogic_react
from quantalogic_react.quantalogic.agent import Agent  # noqa: E402
from quantalogic_react.quantalogic.console_print_events import console_print_events  # noqa: E402
from quantalogic_react.quantalogic.console_print_token import console_print_token  # noqa: E402
from quantalogic_react.quantalogic.create_custom_agent import create_custom_agent  # noqa: E402
from quantalogic_react.quantalogic.event_emitter import EventEmitter  # noqa: E402
from quantalogic_react.quantalogic.memory import AgentMemory, VariableMemory  # noqa: E402

__all__ = [
    "Agent",
    "EventEmitter",
    "AgentMemory",
    "VariableMemory",
    "console_print_events",
    "console_print_token",
    "create_custom_agent"
]
