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
        # Display tools only from enabled toolboxes
        enabled = shell.current_agent.config.enabled_toolboxes or []
        if not enabled:
            return "No toolboxes enabled."
        plugin_manager: PluginManager = shell.current_agent.plugin_manager
        tools_dict = plugin_manager.tools.tools
        # Group only enabled tools by toolbox
        toolbox_dict: dict[str, list[str]] = {tb: [] for tb in enabled}
        for (tb_name, tool_name), _ in tools_dict.items():
            if tb_name in enabled:
                toolbox_dict[tb_name].append(tool_name)
        # Format output with enumeration and bullets for better UX
        lines: list[str] = ["Enabled toolboxes and their tools:"]
        for idx, tb in enumerate(enabled, start=1):
            tools_list = sorted(toolbox_dict.get(tb, []))
            count = len(tools_list)
            lines.append(f"{idx}. {tb} ({count} tool{'' if count == 1 else 's'})")
            if tools_list:
                for tool_name in tools_list:
                    lines.append(f"   - {tool_name}")
            else:
                lines.append("   (no tools)")
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