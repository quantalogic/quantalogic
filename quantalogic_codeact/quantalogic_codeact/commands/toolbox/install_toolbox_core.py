import importlib
import re
import subprocess
from importlib.metadata import entry_points
from importlib.metadata import version as metadata_version
from pathlib import Path

from loguru import logger

from quantalogic_codeact.cli_commands.config_manager import load_global_config, save_global_config
from quantalogic_codeact.codeact.agent_config import Toolbox
from quantalogic_codeact.codeact.plugin_manager import PluginManager


def install_toolbox_core(toolbox_name: str) -> list[str]:
    """Install a toolbox via pip, enable it, update global config, and register tools."""
    messages: list[str] = []
    
    # Determine package name and version
    pkg_path = Path(toolbox_name)
    if pkg_path.exists():
        name = pkg_path.stem
        match = re.match(r"(.+)-(\d+\.\d+\.\d+)", name)
        if match:
            package_name, version = match.group(1), match.group(2)
        else:
            package_name, version = name, "unknown"
    else:
        package_name, version = toolbox_name, "unknown"

    # Install via pip
    try:
        subprocess.run(["uv", "pip", "install", toolbox_name], check=True, capture_output=True, text=True)
        messages.append(f"Package '{package_name}' installed successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install toolbox '{toolbox_name}': {e.stderr}")
        messages.append(f"Failed to install toolbox '{toolbox_name}': {e}")
        return messages

    # Try to get actual version
    try:
        version = importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        logger.warning(f"Could not determine version for '{package_name}'.")

    # Load current config
    cfg = load_global_config()
    original_installed = cfg.installed_toolboxes or []

    try:
        # Clean existing installed entries
        new_installed = [tb for tb in original_installed if tb.package != package_name]

        # Discover entry points for this toolbox
        eps = entry_points(group="quantalogic.tools")
        dist_names = {package_name, package_name.replace("_", "-")}
        installed_eps = [ep for ep in eps if ep.dist.name in dist_names]
        to_enable = [ep.name for ep in installed_eps] or [package_name]

        # Build installed toolbox entries
        installed_entries: list[Toolbox] = []
        for name in to_enable:
            ep = next((e for e in installed_eps if e.name == name), None)
            if ep:
                module = ep.load()
                module_file = getattr(module, "__file__", None)
                path = str(Path(module_file).resolve()) if module_file else None
                pkg = ep.dist.name
                ver = getattr(ep.dist, "version", None) or metadata_version(pkg)
            else:
                pkg = package_name
                try:
                    ver = metadata_version(pkg)
                except Exception:
                    ver = version
                try:
                    mod = importlib.import_module(pkg)
                    module_file = getattr(mod, "__file__", None)
                    path = str(Path(module_file).resolve()) if module_file else None
                except Exception:
                    path = None
            installed_entries.append(Toolbox(
                name=name,
                package=pkg,
                version=ver,
                path=path,
                enabled=True  # Enable by default
            ))

        # Register tools for new toolbox
        plugin_manager_instance = PluginManager()
        for ep in installed_eps:
            try:
                module = ep.load()
                if hasattr(module, "get_tools"):
                    plugin_manager_instance.tools.register_tools_from_module(module, toolbox_name=ep.name)
                    messages.append(f"Tools registered for toolbox '{ep.name}'.")
            except Exception as e:
                logger.warning(f"Could not register tools for '{ep.name}': {e}")
                messages.append(f"Warning: Could not register tools for '{ep.name}': {e}")

        # Update config
        cfg.installed_toolboxes = new_installed + installed_entries

        # Save config
        try:
            save_global_config(cfg)
            messages.append(f"Toolbox '{', '.join(to_enable)}' installed and activated.")
        except Exception as e:
            logger.error(f"Failed to save config after installing '{package_name}': {e}")
            # Rollback: Uninstall the package
            try:
                subprocess.run(["uv", "pip", "uninstall", "-y", package_name], check=True, capture_output=True, text=True)
                messages.append(f"Rolled back installation of '{package_name}' due to config save failure.")
            except subprocess.CalledProcessError as rollback_e:
                logger.error(f"Failed to rollback installation of '{package_name}': {rollback_e.stderr}")
                messages.append(f"Error: Failed to rollback installation of '{package_name}': {rollback_e}")
            # Restore original config state
            cfg.installed_toolboxes = original_installed
            messages.append(f"Error: Failed to save config: {e}. Installation reverted.")
            return messages

        return messages

    except Exception as e:
        logger.error(f"Unexpected error during toolbox installation: {e}")
        # Rollback: Uninstall the package
        try:
            subprocess.run(["uv", "pip", "uninstall", "-y", package_name], check=True, capture_output=True, text=True)
            messages.append(f"Rolled back installation of '{package_name}' due to error.")
        except subprocess.CalledProcessError as rollback_e:
            logger.error(f"Failed to rollback installation of '{package_name}': {rollback_e.stderr}")
            messages.append(f"Error: Failed to rollback installation of '{package_name}': {rollback_e}")
        messages.append(f"Error: Failed to install toolbox '{toolbox_name}': {e}")
        return messages