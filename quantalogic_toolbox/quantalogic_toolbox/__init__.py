from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

try:
    __version__ = _version("quantalogic-toolbox")
except PackageNotFoundError:
    __version__ = "0.8.0"

from .tool import Tool, ToolArgument, ToolDefinition, create_tool

__all__ = [
    "ToolArgument",
    "ToolDefinition",
    "Tool",
    "create_tool",
]
