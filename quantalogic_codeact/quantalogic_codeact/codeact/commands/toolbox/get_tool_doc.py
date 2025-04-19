from quantalogic_codeact.codeact.plugin_manager import PluginManager


async def get_tool_doc(shell, args: list[str]) -> str:
    """Get documentation for a specific tool in a toolbox.

    Args:
        shell: The Shell instance, providing access to the agent's plugin_manager.
        args: List of command arguments (expects toolbox name and tool name).

    Returns:
        str: The tool's documentation or an error message.
    """
    if len(args) < 2:
        return "Usage: /toolbox doc <toolbox_name> <tool_name>"
    toolbox_name, tool_name = args[0], args[1]
    plugin_manager: PluginManager = shell.current_agent.plugin_manager
    try:
        tools_dict = plugin_manager.tools.tools
        tool = tools_dict.get((toolbox_name, tool_name))
        if not tool:
            return f"Tool '{tool_name}' not found in toolbox '{toolbox_name}'."
        return tool.to_docstring()
    except Exception as e:
        if shell.debug:
            shell.logger.exception("Get tool documentation error")
        return f"Error retrieving documentation for tool '{tool_name}' in toolbox '{toolbox_name}': {e}"