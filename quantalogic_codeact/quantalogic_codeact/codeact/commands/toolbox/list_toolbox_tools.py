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
        return "Usage: /toolbox tools <toolbox_name>"
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