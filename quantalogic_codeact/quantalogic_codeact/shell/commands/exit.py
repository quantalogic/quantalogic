from typing import List


async def exit_command(shell, args: List[str]) -> str:
    """Handle the /exit command."""
    raise SystemExit(0)