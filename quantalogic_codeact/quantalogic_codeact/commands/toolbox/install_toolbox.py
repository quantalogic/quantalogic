import asyncio

from quantalogic_codeact.cli_commands.config_manager import load_global_config
from quantalogic_codeact.commands.toolbox.install_toolbox_core import install_toolbox_core


async def install_toolbox(shell, args: list[str]) -> str:
    """Install a toolbox using uv pip install.

    Args:
        shell: The Shell instance, providing context (e.g., debug mode).
        args: List of command arguments (expects a single toolbox name).

    Returns:
        str: A message indicating success or failure.
    """
    if not args:
        return "Usage: /toolbox install <toolbox_name>"
    toolbox_name = args[0]
    # Delegate to core installer for shared logic
    messages = await asyncio.to_thread(install_toolbox_core, toolbox_name)
    # Sync in-memory AgentConfig with global state
    cfg = shell.current_agent.config
    global_cfg = load_global_config()
    cfg.enabled_toolboxes = global_cfg.get("enabled_toolboxes", [])
    cfg.installed_toolboxes = global_cfg.get("installed_toolboxes", [])
    # Reload plugins to register changes
    shell.current_agent.plugin_manager.load_plugins(force=True)
    # Refresh default_tools to include newly installed plugin tools
    shell.current_agent.default_tools = shell.current_agent._get_tools()
    return "\n".join(messages)