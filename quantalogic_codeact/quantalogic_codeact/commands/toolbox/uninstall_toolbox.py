import asyncio

from loguru import logger

from quantalogic_codeact.cli_commands.config_manager import load_global_config
from quantalogic_codeact.commands.toolbox.uninstall_toolbox_core import uninstall_toolbox_core


async def uninstall_toolbox(shell, args: list[str]) -> str:
    """Uninstall a toolbox and sync AgentConfig."""
    if not args:
        return "Usage: /toolbox uninstall <toolbox_name>"
    name = args[0]
    
    # Delegate core uninstall logic
    try:
        messages = await asyncio.to_thread(uninstall_toolbox_core, name)
        if any("Error" in msg for msg in messages):
            return "\n".join(messages)
        
        # Sync AgentConfig with global state
        cfg = shell.current_agent.config
        global_cfg = load_global_config()
        cfg.enabled_toolboxes = global_cfg.enabled_toolboxes or []
        cfg.installed_toolboxes = global_cfg.installed_toolboxes or []
        
        # Reload plugins and refresh default tools
        shell.current_agent.plugin_manager.load_plugins(force=True)
        shell.current_agent.default_tools = shell.current_agent._get_tools()
        
        return "\n".join(messages)
    except Exception as e:
        logger.error(f"Unexpected error during toolbox uninstallation: {e}")
        return f"Error: Failed to uninstall toolbox '{name}': {e}"