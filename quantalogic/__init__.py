"""QuantaLogic package initialization."""

import warnings

# Suppress specific warnings related to Pydantic's V2 configuration changes
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="pydantic.*",
    message=".*config keys have changed in V2:.*|.*'fields' config key is removed in V2.*",
)

# Import public API
from .agent import Agent  # noqa: E402
from .console_print_events import console_print_events  # noqa: E402
from .console_print_token import console_print_token  # noqa: E402
from .event_emitter import EventEmitter  # noqa: E402
from .llm import count_tokens, generate_completion, generate_image  # noqa: E402
from .memory import AgentMemory, VariableMemory  # noqa: E402

__all__ = [
    "Agent",
    "EventEmitter",
    "AgentMemory",
    "VariableMemory",
    "console_print_events",
    "console_print_token",
    "generate_completion",
    "generate_image",
    "count_tokens"
]
