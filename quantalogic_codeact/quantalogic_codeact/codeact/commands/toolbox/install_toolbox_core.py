import importlib
import re
import subprocess
from importlib.metadata import entry_points
from importlib.metadata import version as metadata_version
from pathlib import Path

from quantalogic_codeact.codeact.cli import plugin_manager
from quantalogic_codeact.codeact.cli_commands.config_manager import load_global_config, save_global_config


def install_toolbox_core(toolbox_name: str) -> list[str]:
    """Install a toolbox via pip, update global config, and register tools."""
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
        subprocess.run(["uv", "pip", "install", toolbox_name], check=True)
    except subprocess.CalledProcessError as e:
        messages.append(f"Failed to install toolbox '{toolbox_name}': {e}")
        return messages
    # Try to get actual version
    try:
        version = importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        pass
    # Load and update config
    cfg = load_global_config()
    # Clean existing installed entries
    installed = cfg.get("installed_toolboxes", [])
    new_installed = [tb for tb in installed if not (isinstance(tb, dict) and tb.get("package") == package_name)]
    # Discover entry points for this toolbox
    eps = entry_points(group="quantalogic.tools")
    dist_names = {package_name, package_name.replace("_", "-")}
    installed_eps = [ep for ep in eps if ep.dist.name in dist_names]
    to_enable = [ep.name for ep in installed_eps] or [package_name]
    # Build installed toolbox entries
    installed_entries: list[dict] = []
    for name in to_enable:
        ep = next((e for e in installed_eps if e.name == name), None)
        if ep:
            module = ep.load()
            module_file = getattr(module, "__file__", None)
            path = str(Path(module_file).resolve()) if module_file else None
            pkg = ep.dist.name
            ver = getattr(ep.dist, "version", None) or metadata_version(pkg)
        else:
            pkg = toolbox_name
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
        installed_entries.append({
            "name": name,
            "package": pkg,
            "version": ver,
            "path": path
        })
    # Register tools for new toolbox
    for ep in installed_eps:
        try:
            module = ep.load()
            if hasattr(module, "get_tools"):
                plugin_manager.tools.register_tools_from_module(module, toolbox_name=ep.name)
                messages.append(f"Tools registered for toolbox '{ep.name}'.")
        except Exception as e:
            messages.append(f"Warning: Could not register tools for '{ep.name}': {e}")
    # Update and persist config
    cfg["installed_toolboxes"] = new_installed + installed_entries
    enabled = cfg.get("enabled_toolboxes", []) or []
    for name in to_enable:
        if name not in enabled:
            enabled.append(name)
    cfg["enabled_toolboxes"] = enabled
    save_global_config(cfg)
    messages.append(f"Toolbox '{', '.join(to_enable)}' installed and activated.")
    return messages
