"""Initialization for the Quantalogic MCP Toolbox package."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

try:
    __version__ = _version("quantalogic_toolbox_mcp")
except PackageNotFoundError:
    __version__ = "0.13.0"

from .tools import get_tools

__all__ = ["get_tools"]
