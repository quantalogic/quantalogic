from typing import List

from loguru import logger

from quantalogic_codeact.cli_commands.config_manager import load_global_config, save_global_config


def enable_toolbox_core(toolbox_name: str) -> List[str]:
    """Core logic to enable a toolbox: update global config."""
    messages: List[str] = []
    # Load global configuration
    global_cfg = load_global_config()
    installed = global_cfg.installed_toolboxes or []

    try:
        # Find and enable toolbox
        for tb in installed:
            if tb.name == toolbox_name:
                if tb.enabled:
                    messages.append(f"Toolbox '{toolbox_name}' is already enabled.")
                    return messages
                tb.enabled = True
                messages.append(f"Toolbox '{toolbox_name}' enabled.")
                break
        else:
            messages.append(f"Toolbox '{toolbox_name}' is not installed.")
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