import importlib.metadata
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from quantalogic_codeact.cli_commands.config_manager import load_global_config, save_global_config
from quantalogic_codeact.codeact.agent_config import Toolbox


def find_toolbox_in_environment(toolbox_name: str) -> Optional[Dict[str, str]]:
    """Find a toolbox in the environment that's not registered in config.
    
    Args:
        toolbox_name: Name of the toolbox to look for
        
    Returns:
        Dict with package, version and path if found, None otherwise
    """
    try:
        # Check for entry points in quantalogic.tools group
        entry_points = importlib.metadata.entry_points(group="quantalogic.tools")
        for ep in entry_points:
            if ep.name == toolbox_name:
                module = ep.load()
                module_path = getattr(module, "__file__", None)
                dist = importlib.metadata.distribution(ep.value.split(":")[0])
                return {
                    "package": dist.metadata["Name"],
                    "version": dist.version,
                    "path": str(Path(module_path).resolve()) if module_path else None
                }
                
        # Also search directly in installed packages
        for dist in importlib.metadata.distributions():
            if dist.metadata["Name"] == toolbox_name:
                return {
                    "package": dist.metadata["Name"],
                    "version": dist.version,
                    "path": None  # We don't have the path in this case
                }
        
        return None
    except Exception as e:
        logger.error(f"Error finding toolbox in environment: {e}")
        return None


def enable_toolbox_core(toolbox_name: str) -> List[str]:
    """Core logic to enable a toolbox: update global config."""
    messages: List[str] = []
    # Load global configuration
    global_cfg = load_global_config()
    installed = global_cfg.installed_toolboxes or []

    try:
        # First check if already installed and just needs enabling
        for tb in installed:
            if tb.name == toolbox_name:
                if tb.enabled:
                    messages.append(f"Toolbox '{toolbox_name}' is already enabled.")
                    # Always save config even if no change to ensure persistence
                    save_global_config(global_cfg)
                    return messages
                tb.enabled = True
                messages.append(f"Toolbox '{toolbox_name}' enabled.")
                break
        else:
            # If not in installed_toolboxes, check if it's available in the environment
            toolbox_info = find_toolbox_in_environment(toolbox_name)
            if toolbox_info:
                # Auto-register the toolbox before enabling
                new_toolbox = Toolbox(
                    name=toolbox_name,
                    package=toolbox_info["package"],
                    version=toolbox_info["version"],
                    path=toolbox_info["path"],
                    enabled=True  # Enable it right away
                )
                global_cfg.installed_toolboxes.append(new_toolbox)
                messages.append(f"Toolbox '{toolbox_name}' auto-registered from environment and enabled.")
            else:
                # Try to register all available toolboxes in environment first
                # This helps ensure all available toolboxes are in the config
                registered_new = False
                entry_points = importlib.metadata.entry_points(group="quantalogic.tools")
                for ep in entry_points:
                    # Skip already installed toolboxes
                    if any(tb.name == ep.name for tb in installed):
                        continue
                        
                    # Register this new toolbox
                    env_toolbox = find_toolbox_in_environment(ep.name)
                    if env_toolbox:
                        new_tb = Toolbox(
                            name=ep.name,
                            package=env_toolbox["package"],
                            version=env_toolbox["version"],
                            path=env_toolbox["path"],
                            enabled=False  # Not enabled by default
                        )
                        global_cfg.installed_toolboxes.append(new_tb)
                        registered_new = True
                        logger.info(f"Auto-discovered toolbox '{ep.name}' and added to config.")
                        
                        # If this is the one we're looking for, enable it
                        if ep.name == toolbox_name:
                            new_tb.enabled = True
                            messages.append(f"Toolbox '{toolbox_name}' auto-registered from environment and enabled.")
                            break
                            
                # If we registered new toolboxes but not the one we're looking for
                if registered_new and not any(tb.name == toolbox_name and tb.enabled for tb in global_cfg.installed_toolboxes):
                    messages.append(f"Toolbox '{toolbox_name}' is not installed or available, but discovered other toolboxes.")
                    save_global_config(global_cfg)
                    return messages
                elif not registered_new:
                    messages.append(f"Toolbox '{toolbox_name}' is not installed or available.")
                    return messages

        # Save config
        try:
            save_global_config(global_cfg)
            return messages
        except Exception as e:
            logger.error(f"Failed to save config after enabling '{toolbox_name}': {e}")
            # Rollback: Disable the toolbox
            for tb in installed:
                if tb.name == toolbox_name:
                    tb.enabled = False
                    break
            messages.append(f"Error: Failed to save config: {e}. Enabling reverted.")
            return messages

    except Exception as e:
        logger.error(f"Unexpected error during toolbox enabling: {e}")
        # Rollback: Ensure no changes persist
        messages.append(f"Error: Failed to enable toolbox '{toolbox_name}': {e}")
        return messages