import asyncio
import subprocess
from importlib.metadata import entry_points


async def install_toolbox(shell, args: list[str]) -> str:
    """Install a toolbox using uv pip install.

    Args:
        shell: The Shell instance, providing context (e.g., debug mode).
        args: List of command arguments (expects a single toolbox name).

    Returns:
        str: A message indicating success or failure.
    """
    if not args:
        return "Usage: /toolbox install <toolbox_name>"
    toolbox_name = args[0]
    try:
        await asyncio.to_thread(subprocess.run, ["uv", "pip", "install", toolbox_name], check=True)
        # Immediately detect and enable new toolboxes from entry points
        eps = entry_points(group="quantalogic.tools")
        to_enable = [ep.name for ep in eps]
        if not to_enable:
            to_enable = [toolbox_name]
        cfg = shell.current_agent.config
        if cfg.enabled_toolboxes is None:
            cfg.enabled_toolboxes = []
        for name in to_enable:
            if name not in cfg.enabled_toolboxes:
                cfg.enabled_toolboxes.append(name)
        # Reload plugins to register new toolbox immediately
        shell.current_agent.plugin_manager.load_plugins(force=True)
        return f"Toolbox '{', '.join(to_enable)}' installed and activated."
    except subprocess.CalledProcessError as e:
        if shell.debug:
            shell.logger.exception("Install toolbox error")
        return f"Failed to install toolbox: {e}"