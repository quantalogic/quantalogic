from quantalogic_codeact.cli_commands.config_manager import load_global_config
from quantalogic_codeact.codeact.plugin_manager import PluginManager


async def list_toolbox_tools(shell, args: list[str]) -> str:
    """List tools in a specific toolbox.

    Args:
        shell: The Shell instance, providing access to the agent's plugin_manager.
        args: List of command arguments (expects a single toolbox name).

    Returns:
        str: A formatted string of tool names or an error message.
    """
    if not args:
        plugin_manager: PluginManager = shell.current_agent.plugin_manager
        tools_dict = plugin_manager.tools.tools
        # List all toolboxes, marking enabled ones
        # Always include default toolbox and mark it enabled
        default_tb = "default"
        all_toolboxes = sorted({tb for (tb, _), _ in tools_dict.items()} | {default_tb})
        enabled = set(shell.current_agent.config.enabled_toolboxes or []) | {default_tb}
        lines: list[str] = ["# Toolboxes"]
        
        # Fetch fresh data from the config once to ensure we have latest state
        # This ensures consistent registration status for all toolboxes
        global_cfg = load_global_config()
        registered_toolboxes = {tb.name for tb in global_cfg.installed_toolboxes}
        
        for tb in all_toolboxes:
            # Check if toolbox is registered in config (installed explicitly by user)
            is_registered = tb in registered_toolboxes
            is_default = tb == "default"
            
            # Mark uninstallable status and enabled status
            checkbox = "[X]" if tb in enabled else "[ ]"
            tb_tools = sorted([tool for (tb_name, tool), _ in tools_dict.items() if tb_name == tb])
            count = len(tb_tools)
            # Add status note - default is special, registered means in config, others are available but not in config
            if is_default:
                status_note = ""
            elif is_registered:
                status_note = ""
            else:
                status_note = " (not in config)"
            lines.append(f"- {checkbox} **{tb}{status_note}** ({count} tool{'s' if count != 1 else ''})")
            if tb in enabled and tb_tools:
                for tool_name in tb_tools:
                    lines.append(f"    - {tool_name}")
        return "\n".join(lines)
    toolbox_name = args[0]
    plugin_manager: PluginManager = shell.current_agent.plugin_manager
    try:
        tools_dict = plugin_manager.tools.tools
        tools = sorted([tool_name for (tb_name, tool_name), _ in tools_dict.items() if tb_name == toolbox_name])
        if not tools:
            return f"No tools found in toolbox '{toolbox_name}'."
        return "\n".join(tools)
    except Exception as e:
        if shell.debug:
            shell.logger.exception("List toolbox tools error")
        return f"Error listing tools for toolbox '{toolbox_name}': {e}"