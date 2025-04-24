import asyncio

from quantalogic_codeact.cli_commands.config_manager import load_global_config
from quantalogic_codeact.commands.toolbox.disable_toolbox_core import disable_toolbox_core


async def disable_toolbox(shell, args: list[str]) -> str:
    """Disable a toolbox and sync AgentConfig."""
    if not args:
        return "Usage: /toolbox disable <toolbox_name>"
    name = args[0]
    # Delegate to core logic
    messages = await asyncio.to_thread(disable_toolbox_core, name)
    # Sync in-memory AgentConfig with global state
    cfg = shell.current_agent.config
    global_cfg = load_global_config()
    # Update installed_toolboxes with enabled status from global config
    enabled_toolboxes = set(tb.name for tb in global_cfg.installed_toolboxes if tb.enabled)
    
    # Update agent config's installed_toolboxes
    for i, tb in enumerate(cfg.installed_toolboxes):
        if tb.name in enabled_toolboxes:
            cfg.installed_toolboxes[i].enabled = True
        else:
            cfg.installed_toolboxes[i].enabled = False
    # Reload plugins and refresh default tools
    shell.current_agent.plugin_manager.load_plugins(force=True)
    shell.current_agent.default_tools = shell.current_agent._get_tools()
    return "\n".join(messages)