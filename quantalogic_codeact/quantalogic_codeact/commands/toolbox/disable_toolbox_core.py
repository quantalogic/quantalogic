from typing import List

from loguru import logger

from quantalogic_codeact.cli_commands.config_manager import load_global_config, save_global_config


def disable_toolbox_core(toolbox_name: str) -> List[str]:
    """Core logic to disable a toolbox: update global config."""
    messages: List[str] = []
    # Load global configuration
    global_cfg = load_global_config()
    enabled = global_cfg.enabled_toolboxes or []
    original_enabled = enabled.copy()

    try:
        if toolbox_name not in enabled:
            messages.append(f"Toolbox '{toolbox_name}' is not enabled.")
            return messages

        # Disable toolbox
        new_enabled = [name for name in enabled if name != toolbox_name]
        global_cfg.enabled_toolboxes = new_enabled

        # Save config
        try:
            save_global_config(global_cfg)
            messages.append(f"Toolbox '{toolbox_name}' disabled.")
            return messages
        except Exception as e:
            logger.error(f"Failed to save config after disabling '{toolbox_name}': {e}")
            # Rollback: Restore original enabled_toolboxes
            global_cfg.enabled_toolboxes = original_enabled
            messages.append(f"Error: Failed to save config: {e}. Disabling reverted.")
            return messages

    except Exception as e:
        logger.error(f"Unexpected error during toolbox disabling: {e}")
        # Rollback: Restore original enabled_toolboxes
        global_cfg.enabled_toolboxes = original_enabled
        messages.append(f"Error: Failed to disable toolbox '{toolbox_name}': {e}")
        return messages