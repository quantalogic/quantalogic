from typing import List

from loguru import logger

from quantalogic_codeact.cli_commands.config_manager import load_global_config, save_global_config


def disable_toolbox_core(toolbox_name: str) -> List[str]:
    """Core logic to disable a toolbox: update global config."""
    messages: List[str] = []
    # Load global configuration
    global_cfg = load_global_config()
    installed = global_cfg.installed_toolboxes or []

    try:
        # Find and disable toolbox
        for tb in installed:
            if tb.name == toolbox_name:
                if not tb.enabled:
                    messages.append(f"Toolbox '{toolbox_name}' is already disabled.")
                    return messages
                tb.enabled = False
                messages.append(f"Toolbox '{toolbox_name}' disabled.")
                break
        else:
            messages.append(f"Toolbox '{toolbox_name}' is not installed.")
            return messages

        # Save config
        try:
            save_global_config(global_cfg)
            return messages
        except Exception as e:
            logger.error(f"Failed to save config after disabling '{toolbox_name}': {e}")
            # Rollback: Re-enable the toolbox
            for tb in installed:
                if tb.name == toolbox_name:
                    tb.enabled = True
                    break
            messages.append(f"Error: Failed to save config: {e}. Disabling reverted.")
            return messages

    except Exception as e:
        logger.error(f"Unexpected error during toolbox disabling: {e}")
        # Rollback: Ensure no changes persist
        messages.append(f"Error: Failed to disable toolbox '{toolbox_name}': {e}")
        return messages