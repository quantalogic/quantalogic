from typing import List

from quantalogic_codeact.cli_commands.config_manager import load_global_config


async def installed_toolbox(shell, args: List[str]) -> str:
    """List all installed toolboxes."""
    if args:
        return "Usage: /toolbox installed"
    cfg = load_global_config()
    installed = cfg.installed_toolboxes or []
    if not installed:
        return "No toolboxes installed."
    lines: List[str] = ["Installed toolboxes:"]
    for tb in installed:
        lines.append(f"- {tb.name} (package: {tb.package}, version: {tb.version})")
    return "\n".join(lines)