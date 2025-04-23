from typing import List

from quantalogic_codeact.codeact.cli_commands.config_manager import load_global_config


async def installed_toolbox(shell, args: List[str]) -> str:
    """List all installed toolboxes."""
    if args:
        return "Usage: /toolbox installed"
    cfg = load_global_config()
    installed = cfg.get("installed_toolboxes", []) or []
    if not installed:
        return "No toolboxes installed."
    lines: List[str] = ["Installed toolboxes:"]
    for tb in installed:
        if isinstance(tb, dict):
            name = tb.get("name")
            pkg = tb.get("package")
            ver = tb.get("version")
            lines.append(f"- {name} (package: {pkg}, version: {ver})")
        else:
            lines.append(f"- {tb}")
    return "\n".join(lines)
