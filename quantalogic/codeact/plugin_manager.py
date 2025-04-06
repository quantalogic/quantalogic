"""Plugin management module for dynamically loading components."""

from importlib.metadata import entry_points
from typing import List

from loguru import logger

from quantalogic.tools import Tool

from .executor import Executor
from .reasoner import Reasoner
from .tools_manager import ToolRegistry


class PluginManager:
    """Manages dynamic loading of plugins for tools, reasoners, executors, and CLI commands."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PluginManager, cls).__new__(cls)
            cls._instance.tools = ToolRegistry()
            cls._instance.reasoners = {"default": Reasoner}
            cls._instance.executors = {"default": Executor}
            cls._instance.cli_commands = {}
            cls._instance._plugins_loaded = False
        return cls._instance

    def load_plugins(self, force: bool = False) -> None:
        """Load all plugins from registered entry points, handling duplicates gracefully.
        
        Args:
            force: If True, reload plugins even if they were already loaded
        """
        if self._plugins_loaded and not force:
            logger.debug("Plugins already loaded, skipping reload")
            return
        
        # Clear existing plugins if forcing reload
        if force:
            self.tools = ToolRegistry()
            self.reasoners = {"default": Reasoner}
            self.executors = {"default": Executor}
            self.cli_commands = {}
            self._plugins_loaded = False

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
                            store()
                        else:
                            store[ep.name] = loaded
                            logger.info(f"Loaded plugin {ep.name} for {group}")
                    except ValueError as e:
                        logger.warning(f"Skipping duplicate tool registration for {ep.name}: {e}")
                    except ImportError as e:
                        logger.error(f"Failed to load plugin {ep.name} for {group}: {e}")
            except Exception as e:
                logger.error(f"Failed to retrieve entry points for {group}: {e}")
        self._plugins_loaded = True

    def get_tools(self, force_reload: bool = False) -> List[Tool]:
        """Return all registered tools.
        
        Args:
            force_reload: If True, reload plugins before getting tools
        """
        if force_reload:
            self.load_plugins(force=True)
        return self.tools.get_tools()