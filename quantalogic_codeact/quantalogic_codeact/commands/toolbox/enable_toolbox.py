import asyncio

from loguru import logger

from quantalogic_codeact.cli_commands.config_manager import load_global_config
from quantalogic_codeact.commands.toolbox.enable_toolbox_core import enable_toolbox_core


async def enable_toolbox(shell, args: list[str]) -> str:
    """Enable a toolbox and sync AgentConfig."""
    if not args:
        return "Usage: /toolbox enable <toolbox_name>"
    name = args[0]
    
    # Delegate to core logic
    try:
        messages = await asyncio.to_thread(enable_toolbox_core, name)
        if any("Error" in msg for msg in messages):
            return "\n".join(messages)
        
        # Sync in-memory AgentConfig with global state
        cfg = shell.current_agent.config
        global_cfg = load_global_config()
        cfg.enabled_toolboxes = global_cfg.enabled_toolboxes or []
        cfg.installed_toolboxes = global_cfg.installed_toolboxes or []
        
        # Reload plugins and refresh default tools
        shell.current_agent.plugin_manager.load_plugins(force=True)
        shell.current_agent.default_tools = shell.current_agent._get_tools()
        
        return "\n".join(messages)
    except Exception as e:
        logger.error(f"Unexpected error during toolbox enabling: {e}")
        return f"Error: Failed to enable toolbox '{name}': {e}"