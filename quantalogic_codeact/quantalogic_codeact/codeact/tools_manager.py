"""Tool management module for defining and retrieving agent tools."""

import importlib
import importlib.metadata
import inspect
from typing import Any, List, Optional

from loguru import logger

from quantalogic_toolbox import Tool, create_tool

from .tools import AgentTool, RetrieveStepTool


class ToolRegistry:
    """Manages tool registration with dependency and conflict checking."""
    
    def __init__(self):
        self.tools: dict[tuple[str, str], Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool, checking for conflicts within the same toolbox."""
        try:
            key = (tool.toolbox_name or "default", tool.name)
            if key in self.tools:
                logger.debug(f"Tool '{tool.name}' in toolbox '{tool.toolbox_name or 'default'}' already registered.")
                return
            self.tools[key] = tool
            logger.debug(f"Tool registered: {tool.name} in toolbox {tool.toolbox_name or 'default'}")
        except Exception as e:
            logger.error(f"Failed to register tool {tool.name}: {e}")
            raise

    def get_tools(self) -> List[Tool]:
        """Return all registered tools."""
        try:
            logger.debug(f"Returning {len(self.tools)} tools: {list(self.tools.keys())}")
            return list(self.tools.values())
        except Exception as e:
            logger.error(f"Error retrieving tools: {e}")
            return []

    def register_tools_from_module(self, module, toolbox_name: str) -> None:
        """Register tools from a module, supporting both @create_tool, get_tools, and instance-based tools."""
        try:
            tools_found = False
            logger.debug(f"Processing module {getattr(module, '__name__', str(module))} for toolbox {toolbox_name}")
            # Check for get_tools function to register dependency-free tools
            if hasattr(module, 'get_tools'):
                tool_items = module.get_tools()
                for item in tool_items:
                    if inspect.iscoroutinefunction(item):
                        # Handle async functions
                        tool = create_tool(item)
                        tool.toolbox_name = toolbox_name
                        self.register(tool)
                        logger.debug(f"Registered tool from get_tools: {tool.name} in toolbox {toolbox_name}")
                        tools_found = True
                    elif isinstance(item, Tool):
                        # Handle pre-constructed Tool instances
                        item.toolbox_name = toolbox_name
                        self.register(item)
                        logger.debug(f"Registered Tool instance from get_tools: {item.name} in toolbox {toolbox_name}")
                        tools_found = True
                    elif hasattr(item, 'name') and hasattr(item, 'description'):
                        # Handle instance-based tools (e.g., DynamicTool)
                        if not hasattr(item, 'toolbox_name'):
                            item.toolbox_name = toolbox_name
                        self.register(item)
                        logger.debug(f"Registered instance-based tool: {item.name} in toolbox {toolbox_name}")
                        tools_found = True
                    else:
                        logger.warning(f"Item '{str(item)}' in {getattr(module, '__name__', str(module))} is not a recognized tool type. Skipping.")

            # Register @create_tool-decorated Tool instances
            for name, obj in inspect.getmembers(module):
                if isinstance(obj, Tool) and hasattr(obj, '_func'):
                    obj.toolbox_name = toolbox_name
                    self.register(obj)
                    logger.debug(f"Registered @create_tool tool: {obj.name} from {getattr(module, '__name__', str(module))} in toolbox {toolbox_name}")
                    tools_found = True

            if not tools_found:
                logger.warning(f"No tools found in {getattr(module, '__name__', str(module))}")
        except Exception as e:
            logger.error(f"Failed to register tools from module {getattr(module, '__name__', str(module))}: {e}")
            # Continue without raising to allow other toolboxes to load
            return

    def load_toolboxes(self, toolbox_names: Optional[List[str]] = None) -> None:
        """Load toolboxes from registered entry points, optionally filtering by name."""
        try:
            entry_points = importlib.metadata.entry_points(group="quantalogic.tools")
        except Exception as e:
            logger.error(f"Failed to retrieve entry points: {e}")
            entry_points = []

        try:
            if toolbox_names is not None:
                entry_points = [ep for ep in entry_points if ep.name in toolbox_names]

            logger.debug(f"Found {len(entry_points)} toolbox entry points")
            for ep in entry_points:
                try:
                    module = ep.load()
                    self.register_tools_from_module(module, toolbox_name=ep.name)
                    logger.info(f"Successfully loaded toolbox: {ep.name}")
                except ImportError as e:
                    logger.error(f"Failed to import toolbox {ep.name}: {e}")
                except Exception as e:
                    logger.error(f"Failed to load toolbox {ep.name}: {e}")
        except Exception as e:
            logger.error(f"Error loading toolboxes: {e}")


def get_default_tools(
    model: str,
    history_store: Optional[List[dict]] = None,
    enabled_toolboxes: Optional[List[str]] = None,
    tools_config: Optional[List[dict[str, Any]]] = None
) -> List[Tool]:
    """Dynamically load default tools using the pre-loaded registry from PluginManager."""
    from .cli import plugin_manager

    try:
        plugin_manager.load_plugins()
        registry = plugin_manager.tools
        
        static_tools: List[Tool] = [AgentTool(model=model)]
        if history_store is not None:
            static_tools.append(RetrieveStepTool(history_store))

        for tool in static_tools:
            try:
                registry.register(tool)
            except ValueError as e:
                logger.debug(f"Static tool {tool.name} already registered: {e}")

        # Only filter tools if enabled_toolboxes is explicitly provided and non-empty
        if enabled_toolboxes is not None and enabled_toolboxes:
            tools = [t for t in registry.get_tools() if t.toolbox_name in enabled_toolboxes]
        else:
            tools = registry.get_tools()

        if tools_config:
            filtered_tools = []
            processed_names = set()
            for tool_conf in tools_config:
                if tool_conf.get("enabled", True):
                    tool = next((t for t in tools if t.name == tool_conf["name"] or t.toolbox_name == tool_conf["name"]), None)
                    if tool and tool.name not in processed_names:
                        for key, value in tool_conf.items():
                            if key not in ["name", "enabled"]:
                                setattr(tool, key, value)
                        filtered_tools.append(tool)
                        processed_names.add(tool.name)
            for tool in tools:
                if tool.name not in processed_names:
                    filtered_tools.append(tool)
            tools = filtered_tools
        
        logger.info(f"Loaded {len(tools)} default tools: {[(tool.toolbox_name or 'default', tool.name) for tool in tools]}")
        return tools
    except Exception as e:
        logger.error(f"Failed to load default tools: {e}")
        return []