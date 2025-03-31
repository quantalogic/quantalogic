"""Plugin management module for dynamically loading components."""

from importlib.metadata import entry_points
from typing import Callable, Dict, List, Type

from loguru import logger

from quantalogic.tools import Tool

from .executor import BaseExecutor
from .reasoner import BaseReasoner
from .tools_manager import ToolRegistry


class PluginManager:
    """Manages dynamic loading of plugins for tools, reasoners, executors, and CLI commands."""
    def __init__(self):
        self.tools = ToolRegistry()
        self.reasoners: Dict[str, Type[BaseReasoner]] = {"default": BaseReasoner}
        self.executors: Dict[str, Type[BaseExecutor]] = {"default": BaseExecutor}
        self.cli_commands: Dict[str, Callable] = {}

    def load_plugins(self) -> None:
        """Load all plugins from registered entry points."""
        for group, store in [
            ("quantalogic.tools", self.tools.load_toolboxes),
            ("quantalogic.reasoners", self.reasoners),
            ("quantalogic.executors", self.executors),
            ("quantalogic.cli", self.cli_commands),
        ]:
            try:
                eps = entry_points(group=group)
                logger.debug(f"Found {len(eps)} entry points for group {group}")
                for ep in eps:
                    try:
                        loaded = ep.load()
                        if group == "quantalogic.tools":
                            store()  # ToolRegistry handles its own loading
                        else:
                            store[ep.name] = loaded
                            logger.info(f"Loaded plugin {ep.name} for {group}")
                    except ImportError as e:
                        logger.error(f"Failed to load plugin {ep.name} for {group}: {e}")
            except Exception as e:
                logger.error(f"Failed to retrieve entry points for {group}: {e}")

    def get_tools(self) -> List[Tool]:
        """Return all registered tools."""
        return self.tools.get_tools()