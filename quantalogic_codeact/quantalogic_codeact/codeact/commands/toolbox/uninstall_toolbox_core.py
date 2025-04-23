import subprocess
from typing import List

import quantalogic_codeact.codeact.cli_commands.config_manager as config_manager


def uninstall_toolbox_core(toolbox_name: str) -> List[str]:
    """Core logic to uninstall a toolbox: pip uninstall, update global config."""
    messages: List[str] = []
    # Load global configuration
    global_cfg = config_manager.load_global_config()
    installed = global_cfg.get("installed_toolboxes", []) or []
    # Find entries by toolbox name
    entries = [tb for tb in installed if isinstance(tb, dict) and tb.get("name") == toolbox_name]
    if entries:
        # Uninstall each package and remove from config
        for tb in entries:
            package = tb.get("package") or toolbox_name
            try:
                subprocess.run(["uv", "pip", "uninstall", package], check=True)
                messages.append(f"Package '{package}' uninstalled.")
            except subprocess.CalledProcessError as e:
                messages.append(f"Failed to uninstall package '{package}': {e}")
        # Update config: remove uninstalled entries
        new_installed = [tb for tb in installed if not (isinstance(tb, dict) and tb.get("name") == toolbox_name)]
        global_cfg["installed_toolboxes"] = new_installed
        # Disable toolbox
        enabled = global_cfg.get("enabled_toolboxes", []) or []
        enabled = [name for name in enabled if name != toolbox_name]
        global_cfg["enabled_toolboxes"] = enabled
        config_manager.save_global_config(global_cfg)
        messages.append(f"Toolbox '{toolbox_name}' removed from global config.")
        return messages
    # Else, check by package name
    package_entries = [tb for tb in installed if isinstance(tb, dict) and tb.get("package") == toolbox_name]
    if package_entries:
        for tb in package_entries:
            package = toolbox_name
            try:
                subprocess.run(["uv", "pip", "uninstall", package], check=True)
                messages.append(f"Package '{package}' uninstalled.")
            except subprocess.CalledProcessError as e:
                messages.append(f"Failed to uninstall package '{package}': {e}")
        names = ", ".join(tb.get("name") for tb in package_entries)
        # Update config: remove entries by package
        new_installed = [tb for tb in installed if not (isinstance(tb, dict) and tb.get("package") == toolbox_name)]
        global_cfg["installed_toolboxes"] = new_installed
        # Disable toolboxes
        enabled = global_cfg.get("enabled_toolboxes", []) or []
        updated = [name for name in enabled if name not in [tb.get("name") for tb in package_entries]]
        global_cfg["enabled_toolboxes"] = updated
        config_manager.save_global_config(global_cfg)
        messages.append(f"Toolbox(es) '{names}' removed from global config.")
        return messages
    # Not found
    messages.append(f"No toolbox or package '{toolbox_name}' found to uninstall.")
    return messages
