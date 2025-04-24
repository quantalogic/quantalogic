import subprocess
from typing import List

from loguru import logger

from quantalogic_codeact.cli_commands.config_manager import load_global_config, save_global_config


def uninstall_toolbox_core(toolbox_name: str) -> List[str]:
    """Core logic to uninstall a toolbox: pip uninstall, update global config."""
    messages: List[str] = []
    # Load global configuration
    global_cfg = load_global_config()
    installed = global_cfg.installed_toolboxes or []
    enabled = global_cfg.enabled_toolboxes or []
    original_installed = installed.copy()
    original_enabled = enabled.copy()

    try:
        # Find entries by toolbox name
        entries = [tb for tb in installed if tb.name == toolbox_name]
        if entries:
            # Uninstall each package and update config
            for tb in entries:
                package = tb.package
                try:
                    subprocess.run(["uv", "pip", "uninstall", "-y", package], check=True, capture_output=True, text=True)
                    messages.append(f"Package '{package}' uninstalled.")
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to uninstall package '{package}': {e.stderr}")
                    messages.append(f"Failed to uninstall package '{package}': {e}")
                    return messages  # Exit early if uninstall fails

            # Update config: remove uninstalled entries
            new_installed = [tb for tb in installed if tb.name != toolbox_name]
            global_cfg.installed_toolboxes = new_installed
            # Disable toolbox
            new_enabled = [name for name in enabled if name != toolbox_name]
            global_cfg.enabled_toolboxes = new_enabled

            # Save config
            try:
                save_global_config(global_cfg)
                messages.append(f"Toolbox '{toolbox_name}' removed from global config.")
                return messages
            except Exception as e:
                logger.error(f"Failed to save config after uninstalling '{toolbox_name}': {e}")
                # Rollback: Restore original config state
                global_cfg.installed_toolboxes = original_installed
                global_cfg.enabled_toolboxes = original_enabled
                messages.append(f"Error: Failed to save config: {e}. Uninstallation reverted.")
                return messages

        # Else, check by package name
        package_entries = [tb for tb in installed if tb.package == toolbox_name]
        if package_entries:
            for tb in package_entries:
                package = toolbox_name
                try:
                    subprocess.run(["uv", "pip", "uninstall", "-y", package], check=True, capture_output=True, text=True)
                    messages.append(f"Package '{package}' uninstalled.")
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to uninstall package '{package}': {e.stderr}")
                    messages.append(f"Failed to uninstall package '{package}': {e}")
                    return messages  # Exit early if uninstall fails

            names = ", ".join(tb.name for tb in package_entries)
            # Update config: remove entries by package
            new_installed = [tb for tb in installed if tb.package != toolbox_name]
            global_cfg.installed_toolboxes = new_installed
            # Disable toolboxes
            new_enabled = [name for name in enabled if name not in [tb.name for tb in package_entries]]
            global_cfg.enabled_toolboxes = new_enabled

            # Save config
            try:
                save_global_config(global_cfg)
                messages.append(f"Toolbox(es) '{names}' removed from global config.")
                return messages
            except Exception as e:
                logger.error(f"Failed to save config after uninstalling '{toolbox_name}': {e}")
                # Rollback: Restore original config state
                global_cfg.installed_toolboxes = original_installed
                global_cfg.enabled_toolboxes = original_enabled
                messages.append(f"Error: Failed to save config: {e}. Uninstallation reverted.")
                return messages

        # Not found
        messages.append(f"No toolbox or package '{toolbox_name}' found to uninstall.")
        return messages

    except Exception as e:
        logger.error(f"Unexpected error during toolbox uninstallation: {e}")
        # Rollback: Restore original config state
        global_cfg.installed_toolboxes = original_installed
        global_cfg.enabled_toolboxes = original_enabled
        messages.append(f"Error: Failed to uninstall toolbox '{toolbox_name}': {e}")
        return messages