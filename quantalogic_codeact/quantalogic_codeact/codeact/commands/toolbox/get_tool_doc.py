async def get_tool_doc(shell, args: list[str]) -> str:
    """Get documentation for a specific tool in a toolbox.

    Args:
        shell: The Shell instance, providing access to the agent's plugin_manager.
        args: List of command arguments (expects toolbox name and tool name).

    Returns:
        str: The tool's documentation or an error message.
    """
    # Use the agent's default_tools (static + enabled plugin tools)
    tools = shell.current_agent.default_tools
    # Group docs by toolbox name
    toolbox_docs: dict[str, list[str]] = {}
    for tool in tools:
        tb_name = tool.toolbox_name or "default"
        doc = tool.to_docstring()
        md = f"### {tool.name}\n```python\n{doc}\n```"
        toolbox_docs.setdefault(tb_name, []).append(md)
    if not toolbox_docs:
        return "No tool documentation available."
    # No args: show docs for all toolboxes
    if len(args) == 0:
        md_lines: list[str] = []
        for tb in sorted(toolbox_docs):
            md_lines.append(f"## {tb}")
            for doc_md in toolbox_docs[tb]:
                md_lines.append(doc_md)
                md_lines.append("")
        return "\n".join(md_lines).strip()
    # Single arg: specific toolbox
    if len(args) == 1:
        toolbox_name = args[0]
        docs = toolbox_docs.get(toolbox_name, [])
        if not docs:
            return f"No tools found in toolbox '{toolbox_name}'."
        return "\n\n".join(docs)
    # Two args: specific tool in toolbox
    toolbox_name, tool_name = args[0], args[1]
    for tool in tools:
        if (tool.toolbox_name or "default") == toolbox_name and tool.name == tool_name:
            return f"```python\n{tool.to_docstring()}\n```"
    return f"Tool '{tool_name}' not found in toolbox '{toolbox_name}'."