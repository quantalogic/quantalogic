from typing import List

import quantalogic_codeact.cli_commands.config_manager as config_manager


def enable_toolbox_core(toolbox_name: str) -> List[str]:
    """Core logic to enable a toolbox: update global config."""
    messages: List[str] = []
    # Load global configuration
    global_cfg = config_manager.load_global_config()
    installed = global_cfg.get("installed_toolboxes", []) or []
    # Determine installed toolbox names
    installed_names = [tb.get("name") if isinstance(tb, dict) else tb for tb in installed]
    if toolbox_name not in installed_names:
        messages.append(f"Toolbox '{toolbox_name}' is not installed.")
        return messages
    # Enable toolbox
    enabled = global_cfg.get("enabled_toolboxes", []) or []
    new_enabled = enabled.copy()
    if toolbox_name in new_enabled:
        messages.append(f"Toolbox '{toolbox_name}' is already enabled.")
    else:
        new_enabled.append(toolbox_name)
        messages.append(f"Toolbox '{toolbox_name}' enabled.")
    global_cfg["enabled_toolboxes"] = new_enabled
    config_manager.save_global_config(global_cfg)
    return messages
