import asyncio
import subprocess


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
        return f"Toolbox '{toolbox_name}' installed. Please restart the shell to use it."
    except subprocess.CalledProcessError as e:
        if shell.debug:
            shell.logger.exception("Install toolbox error")
        return f"Failed to install toolbox: {e}"