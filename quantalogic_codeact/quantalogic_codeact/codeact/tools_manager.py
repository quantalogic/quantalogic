"""Tool management module for defining and retrieving agent tools."""

import importlib
import importlib.metadata
import inspect
from typing import List, Optional

import loguru

from quantalogic_codeact.codeact.agent_config import Toolbox
from quantalogic_toolbox import Tool, create_tool

from .tools import AgentTool, RetrieveMessageTool


class ToolRegistry:
    """Manages tool registration with dependency and conflict checking."""
    
    def __init__(self):
        self.tools: dict[tuple[str, str], Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool, checking for conflicts within the same toolbox."""
        try:
            key = (tool.toolbox_name or "default", tool.name)
            if key in self.tools:
                loguru.logger.debug(f"Tool '{tool.name}' in toolbox '{tool.toolbox_name or 'default'}' already registered.")
                return
            self.tools[key] = tool
            loguru.logger.debug(f"Tool registered: {tool.name} in toolbox {tool.toolbox_name or 'default'}")
        except Exception as e:
            loguru.logger.error(f"Failed to register tool {tool.name}: {e}")
            raise

    def get_tools(self) -> List[Tool]:
        """Return all registered tools."""
        try:
            loguru.logger.debug(f"Returning {len(self.tools)} tools: {list(self.tools.keys())}")
            return list(self.tools.values())
        except Exception as e:
            loguru.logger.error(f"Error retrieving tools: {e}")
            return []

    def register_tools_from_module(self, module, toolbox_name: str) -> None:
        """Register tools from a module, supporting both @create_tool, get_tools, and instance-based tools."""
        try:
            tools_found = False
            loguru.logger.debug(f"Processing module {getattr(module, '__name__', str(module))} for toolbox {toolbox_name}")
            # Check for get_tools function to register dependency-free tools
            if hasattr(module, 'get_tools'):
                tool_items = module.get_tools()
                for item in tool_items:
                    if inspect.iscoroutinefunction(item):
                        # Handle async functions
                        tool = create_tool(item)
                        tool.toolbox_name = toolbox_name
                        
                        # Preserve confirmation attributes from original function
                        if hasattr(item, 'requires_confirmation'):
                            tool.requires_confirmation = item.requires_confirmation
                            loguru.logger.debug(f"Preserved requires_confirmation={item.requires_confirmation} for tool {tool.name}")
                        
                        if hasattr(item, 'confirmation_message'):
                            tool.confirmation_message = item.confirmation_message
                            loguru.logger.debug(f"Preserved confirmation_message for tool {tool.name}")
                        
                        self.register(tool)
                        loguru.logger.debug(f"Registered tool from get_tools: {tool.name} in toolbox {toolbox_name}")
                        tools_found = True
                    elif isinstance(item, Tool):
                        # Handle pre-constructed Tool instances
                        item.toolbox_name = toolbox_name
                        self.register(item)
                        loguru.logger.debug(f"Registered Tool instance from get_tools: {item.name} in toolbox {toolbox_name}")
                        tools_found = True
                    elif hasattr(item, 'name') and hasattr(item, 'description'):
                        # Handle instance-based tools (e.g., DynamicTool)
                        if not hasattr(item, 'toolbox_name'):
                            item.toolbox_name = toolbox_name
                        self.register(item)
                        loguru.logger.debug(f"Registered instance-based tool: {item.name} in toolbox {toolbox_name}")
                        tools_found = True
                    else:
                        loguru.logger.warning(f"Item '{str(item)}' in {getattr(module, '__name__', str(module))} is not a recognized tool type. Skipping.")

            # Register @create_tool-decorated Tool instances
            for name, obj in inspect.getmembers(module):
                if isinstance(obj, Tool) and hasattr(obj, '_func'):
                    obj.toolbox_name = toolbox_name
                    
                    # Check if the original function has confirmation attributes and preserve them
                    if hasattr(obj._func, 'requires_confirmation'):
                        obj.requires_confirmation = obj._func.requires_confirmation
                        loguru.logger.debug(f"Preserved requires_confirmation={obj.requires_confirmation} for tool {obj.name}")
                    
                    if hasattr(obj._func, 'confirmation_message'):
                        obj.confirmation_message = obj._func.confirmation_message
                        loguru.logger.debug(f"Preserved confirmation_message for tool {obj.name}")
                        
                    # Add get_confirmation_message method if it doesn't exist
                    if not hasattr(obj, 'get_confirmation_message'):
                        def get_confirmation_message(self=obj):
                            if hasattr(self, 'confirmation_message'):
                                if callable(self.confirmation_message):
                                    return self.confirmation_message()
                                return self.confirmation_message
                            return None
                        obj.get_confirmation_message = get_confirmation_message
                    
                    self.register(obj)
                    loguru.logger.debug(f"Registered @create_tool tool: {obj.name} from {getattr(module, '__name__', str(module))} in toolbox {toolbox_name}")
                    tools_found = True

            if not tools_found:
                loguru.logger.warning(f"No tools found in {getattr(module, '__name__', str(module))}")
        except Exception as e:
            loguru.logger.error(f"Failed to register tools from module {getattr(module, '__name__', str(module))}: {e}")
            # Continue without raising to allow other toolboxes to load
            return

    def load_toolboxes(self, toolbox_names: List[str] = []) -> None:
        """Load toolboxes from registered entry points, optionally filtering by name."""
        try:
            entry_points = importlib.metadata.entry_points(group="quantalogic.tools")
        except Exception as e:
            loguru.logger.error(f"Failed to retrieve entry points: {e}")
            entry_points = []

        try:
            if toolbox_names:  # Only filter if toolbox_names is non-empty
                entry_points = [ep for ep in entry_points if ep.name in toolbox_names]
            # If no toolbox_names specified, load all available toolboxes
            loguru.logger.debug(f"Found {len(entry_points)} toolbox entry points")
            for ep in entry_points:
                try:
                    module = ep.load()
                    # normalize toolbox names to valid Python identifiers
                    normalized = ep.name.replace('-', '_')
                    self.register_tools_from_module(module, toolbox_name=normalized)
                    loguru.logger.info(f"Successfully loaded toolbox: {ep.name}")
                except ImportError as e:
                    loguru.logger.error(f"Failed to import toolbox {ep.name}: {e}")
                except Exception as e:
                    loguru.logger.error(f"Failed to load toolbox {ep.name}: {e}")
        except Exception as e:
            loguru.logger.error(f"Error loading toolboxes: {e}")


def get_default_tools(
    model: str,
    history_store: Optional[List[dict]] = None,
    enabled_toolboxes: Optional[List[str]] = None,
    installed_toolboxes: Optional[List[Toolbox]]=None
) -> List[Tool]:
    """Dynamically load default tools using the pre-loaded registry from PluginManager."""
    from quantalogic_codeact.cli import plugin_manager

    try:
        plugin_manager.load_plugins()
        registry = plugin_manager.tools
        
        static_tools: List[Tool] = [
            AgentTool(model=model),
            RetrieveMessageTool(history_store or []),
        ]

        # Log available tools before filtering
        available_tools = registry.get_tools()
        loguru.logger.debug(f"Available tools in registry: {[(t.toolbox_name or 'default', t.name) for t in available_tools]}")
        loguru.logger.debug(f"Enabled toolboxes: {enabled_toolboxes}")

        for tool in static_tools:
            try:
                registry.register(tool)
            except ValueError as e:
                loguru.logger.debug(f"Static tool {tool.name} already registered: {e}")

        # Filter plugin tools: only load toolboxes explicitly enabled (None => none)
        if enabled_toolboxes:
            plugin_tools = [t for t in registry.get_tools() if t.toolbox_name in enabled_toolboxes]
        else:
            plugin_tools = []

        # Log filtered plugin tools
        loguru.logger.debug(f"Filtered plugin tools: {[(t.toolbox_name or 'default', t.name) for t in plugin_tools]}")
        
        # Log static and plugin tools separately
        loguru.logger.info(f"Static tools loaded: {[(t.toolbox_name or 'default', t.name) for t in static_tools]}")
        loguru.logger.info(f"Plugin tools loaded: {[(t.toolbox_name or 'default', t.name) for t in plugin_tools]}")

        # Apply per-toolbox configurations
        # Flatten tool_configs from enabled toolboxes
        tool_confs = []
        if installed_toolboxes:
            for tb in installed_toolboxes:
                if tb.enabled:
                    tool_confs.extend(tb.tool_configs or [])
        if tool_confs:
            filtered_plugin_tools: List[Tool] = []
            processed = set()
            for tc in tool_confs:
                if tc.enabled:
                    tool = next((t for t in plugin_tools if t.name == tc.name or t.toolbox_name == tc.name), None)
                    if tool and tool.name not in processed:
                        for key, value in tc.config.items():
                            setattr(tool, key, value)
                        filtered_plugin_tools.append(tool)
                        processed.add(tool.name)
            # Add remaining
            for tool in plugin_tools:
                if tool.name not in processed:
                    filtered_plugin_tools.append(tool)
            plugin_tools = filtered_plugin_tools

        # Always include static tools, ensuring no duplicates
        tools = static_tools.copy()
        for t in plugin_tools:
            if t.name not in {tool.name for tool in tools}:
                tools.append(t)
        
        loguru.logger.info(f"Loaded {len(tools)} default tools: {[(tool.toolbox_name or 'default', tool.name) for tool in tools]}")
        return tools
    except Exception as e:
        loguru.logger.error(f"Failed to load default tools: {e}")
        return []