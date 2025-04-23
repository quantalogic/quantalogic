import asyncio

from quantalogic_codeact.codeact.cli_commands.config_manager import load_global_config
from quantalogic_codeact.codeact.commands.toolbox.uninstall_toolbox_core import uninstall_toolbox_core


async def uninstall_toolbox(shell, args: list[str]) -> str:
    """Uninstall a toolbox and sync AgentConfig."""
    if not args:
        return "Usage: /toolbox uninstall <toolbox_name>"
    name = args[0]
    # Delegate core uninstall logic
    messages = await asyncio.to_thread(uninstall_toolbox_core, name)
    # Sync AgentConfig with global state
    cfg = shell.current_agent.config
    global_cfg = load_global_config()
    cfg.enabled_toolboxes = global_cfg.get("enabled_toolboxes", [])
    cfg.installed_toolboxes = global_cfg.get("installed_toolboxes", [])
    # Reload plugins and refresh default tools
    shell.current_agent.plugin_manager.load_plugins(force=True)
    shell.current_agent.default_tools = shell.current_agent._get_tools()
    return "\n".join(messages)