import asyncio
import subprocess


async def uninstall_toolbox(shell, args: list[str]) -> str:
    """Uninstall a toolbox using uv pip uninstall.

    Args:
        shell: The Shell instance, providing context (e.g., debug mode).
        args: List of command arguments (expects a single toolbox name).

    Returns:
        str: A message indicating success or failure.
    """
    if not args:
        return "Usage: /toolbox uninstall <toolbox_name>"
    toolbox_name = args[0]
    try:
        await asyncio.to_thread(subprocess.run, ["uv", "pip", "uninstall", toolbox_name], check=True)
        # Immediately disable toolbox and reload plugins
        cfg = shell.current_agent.config
        if cfg.enabled_toolboxes and toolbox_name in cfg.enabled_toolboxes:
            cfg.enabled_toolboxes.remove(toolbox_name)
        shell.current_agent.plugin_manager.load_plugins(force=True)
        return f"Toolbox '{toolbox_name}' uninstalled and deactivated."
    except subprocess.CalledProcessError as e:
        if shell.debug:
            shell.logger.exception("Uninstall toolbox error")
        return f"Failed to uninstall toolbox: {e}"