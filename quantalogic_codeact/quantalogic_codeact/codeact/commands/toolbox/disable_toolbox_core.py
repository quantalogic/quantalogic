from typing import List

import quantalogic_codeact.codeact.cli_commands.config_manager as config_manager


def disable_toolbox_core(toolbox_name: str) -> List[str]:
    """Core logic to disable a toolbox: update global config."""
    messages: List[str] = []
    # Load global configuration
    global_cfg = config_manager.load_global_config()
    enabled = global_cfg.get("enabled_toolboxes", []) or []
    if toolbox_name not in enabled:
        messages.append(f"Toolbox '{toolbox_name}' is not enabled.")
        return messages
    # Disable toolbox
    new_enabled = [name for name in enabled if name != toolbox_name]
    global_cfg["enabled_toolboxes"] = new_enabled
    config_manager.save_global_config(global_cfg)
    messages.append(f"Toolbox '{toolbox_name}' disabled.")
    return messages
