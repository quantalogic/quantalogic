import asyncio

from loguru import logger

from quantalogic_codeact.cli_commands.config_manager import load_global_config
from quantalogic_codeact.commands.toolbox.disable_toolbox_core import disable_toolbox_core


async def disable_toolbox(shell, args: list[str]) -> str:
    """Disable a toolbox and sync AgentConfig."""
    if not args:
        return "Usage: /toolbox disable <toolbox_name>"
    name = args[0]
    
    # Delegate to core logic
    try:
        messages = await asyncio.to_thread(disable_toolbox_core, name)
        if any("Error" in msg for msg in messages):
            return "\n".join(messages)
        
        # Reload global config to get latest changes
        global_cfg = load_global_config()
        
        # Get a fresh reference to the agent config
        cfg = shell.current_agent.config
        
        # Synchronize in-memory AgentConfig with global state
        enabled_toolboxes = set(tb.name for tb in global_cfg.installed_toolboxes if tb.enabled)
        
        # Handle any new toolboxes that may have been auto-discovered
        agent_toolbox_names = {tb.name for tb in cfg.installed_toolboxes}
        
        # Add missing toolboxes from global config to agent config
        for tb in global_cfg.installed_toolboxes:
            if tb.name not in agent_toolbox_names:
                logger.info(f"Adding toolbox '{tb.name}' to agent config")
                cfg.installed_toolboxes.append(tb)
        
        # Update enabled status for all toolboxes
        for i, tb in enumerate(cfg.installed_toolboxes):
            tb.enabled = tb.name in enabled_toolboxes
        
        # Save agent config to ensure changes persist
        from quantalogic_codeact.cli_commands.config_manager import save_global_config
        save_global_config(cfg)
        
        # Reload plugins and refresh default tools
        shell.current_agent.plugin_manager.load_plugins(force=True)
        shell.current_agent.refresh_tools()
        
        return "\n".join(messages)
    except Exception as e:
        logger.error(f"Unexpected error during toolbox disabling: {e}")
        return f"Error: Failed to disable toolbox '{name}': {e}"