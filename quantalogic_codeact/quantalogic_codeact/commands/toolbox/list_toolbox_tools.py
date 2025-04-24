from pathlib import Path

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
        # Gather toolbox metadata
        plugin_manager: PluginManager = shell.current_agent.plugin_manager
        tools_dict = plugin_manager.tools.tools
        default_tb = "default"
        all_toolboxes = sorted({tb for (tb, _), _ in tools_dict.items()} | {default_tb})
        enabled = set(shell.current_agent.config.enabled_toolboxes or []) | {default_tb}
        global_cfg = load_global_config()
        installed = {tb.name: tb for tb in global_cfg.installed_toolboxes}
        # Build data rows
        rows = []
        for tb in all_toolboxes:
            mark = "X" if tb in enabled else ""
            count = sum(1 for (name, _), _ in tools_dict.items() if name == tb)
            version = installed[tb].version if tb in installed else ""
            loc = (installed[tb].path or "") if tb in installed else ""
            if tb == default_tb:
                loc = str(Path(__file__).parent.parent.parent)
            if loc.startswith(str(Path.home())):
                loc = "~" + loc[len(str(Path.home())):]
            rows.append([mark, tb, str(count), version, loc])
        # Summary table of toolboxes
        headers = ["Enabled", "Toolbox", "Version", "Location"]
        widths = [
            max(len(headers[0]), *(len(r[0]) for r in rows)),
            max(len(headers[1]), *(len(r[1]) for r in rows)),
            max(len(headers[2]), *(len(r[3]) for r in rows)),
            max(len(headers[3]), *(len(r[4]) for r in rows)),
        ]
        lines = ["## Toolboxes", ""]
        # Table header and separator
        header_row = "| " + " | ".join(headers[i].ljust(widths[i]) for i in range(4)) + " |"
        sep_row = "| " + " | ".join("-" * widths[i] for i in range(4)) + " |"
        lines.extend([header_row, sep_row])
        # Data rows
        for r in rows:
            status = "[X]" if r[0] == "X" else "[ ]"
            lines.append(
                "| " + " | ".join([
                    status.ljust(widths[0]),
                    r[1].ljust(widths[1]),
                    r[3].ljust(widths[2]),
                    r[4].ljust(widths[3]),
                ]) + " |"
            )
        lines.append("")
        # Detailed nested list of tools
        for tb in all_toolboxes:
            status = "[X]" if tb in enabled else "[ ]"
            lines.append(f"- {status} **{tb}**")
            for (name, tool), _ in sorted(tools_dict.items()):
                if name == tb:
                    lines.append(f"    - {tool}")
            lines.append("")
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