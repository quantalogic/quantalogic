from typing import List

from loguru import logger

from quantalogic_codeact.cli_commands.config_manager import load_global_config, save_global_config


def enable_toolbox_core(toolbox_name: str) -> List[str]:
    """Core logic to enable a toolbox: update global config."""
    messages: List[str] = []
    # Load global configuration
    global_cfg = load_global_config()
    installed = global_cfg.installed_toolboxes or []
    enabled = global_cfg.enabled_toolboxes or []
    original_enabled = enabled.copy()

    try:
        # Determine installed toolbox names
        installed_names = [tb.name for tb in installed]
        if toolbox_name not in installed_names:
            messages.append(f"Toolbox '{toolbox_name}' is not installed.")
            return messages

        # Enable toolbox
        new_enabled = enabled.copy()
        if toolbox_name in new_enabled:
            messages.append(f"Toolbox '{toolbox_name}' is already enabled.")
            return messages

        new_enabled.append(toolbox_name)
        global_cfg.enabled_toolboxes = new_enabled

        # Save config
        try:
            save_global_config(global_cfg)
            messages.append(f"Toolbox '{toolbox_name}' enabled.")
            return messages
        except Exception as e:
            logger.error(f"Failed to save config after enabling '{toolbox_name}': {e}")
            # Rollback: Restore original enabled_toolboxes
            global_cfg.enabled_toolboxes = original_enabled
            messages.append(f"Error: Failed to save config: {e}. Enabling reverted.")
            return messages

    except Exception as e:
        logger.error(f"Unexpected error during toolbox enabling: {e}")
        # Rollback: Restore original enabled_toolboxes
        global_cfg.enabled_toolboxes = original_enabled
        messages.append(f"Error: Failed to enable toolbox '{toolbox_name}': {e}")
        return messages