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
        # Show docs for all tools by toolbox if no arguments
        plugin_manager: PluginManager = shell.current_agent.plugin_manager
        tools_dict = plugin_manager.tools.tools
        toolbox_docs: dict[str, list[str]] = {}
        for (tb_name, _), tool in tools_dict.items():
            # Always use to_docstring for markdown formatting
            doc = tool.to_docstring()
            md = f"### {tool.name}\n```python\n{doc}\n```"
            toolbox_docs.setdefault(tb_name, []).append(md)
        if not toolbox_docs:
            return "No tool documentation available."
        # No args: show all toolboxes
        if len(args) == 0:
            md_lines: list[str] = []
            for tb in sorted(toolbox_docs):
                md_lines.append(f"## {tb}")
                for doc_md in toolbox_docs[tb]:
                    md_lines.append(doc_md)
                    md_lines.append("")
            return "\n".join(md_lines).strip()
        # Single arg: specific toolbox
        toolbox_name = args[0]
        docs = toolbox_docs.get(toolbox_name, [])
        if not docs:
            return f"No tools found in toolbox '{toolbox_name}'."
        return "\n\n".join(docs)
    toolbox_name, tool_name = args[0], args[1]
    plugin_manager: PluginManager = shell.current_agent.plugin_manager
    try:
        tools_dict = plugin_manager.tools.tools
        tool = tools_dict.get((toolbox_name, tool_name))
        if not tool:
            return f"Tool '{tool_name}' not found in toolbox '{toolbox_name}'."
        # Wrap the docstring in a code block for markdown
        doc = tool.to_docstring()
        return f"```python\n{doc}\n```"
    except Exception as e:
        if shell.debug:
            shell.logger.exception("Get tool documentation error")
        return f"Error retrieving documentation for tool '{tool_name}' in toolbox '{toolbox_name}': {e}"