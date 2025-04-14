"""Help command implementation."""
from typing import List


async def help_command(shell, args: List[str]) -> str:
    """Display help text, including mode information."""
    if args:
        command = args[0]
        if command in shell.command_registry.commands:
            return shell.command_registry.commands[command]["help"]
        return f"Command '/{command}' not found."
    
    help_text = "Available commands:\n" + "\n".join(
        f"- /{cmd}: {info['help']}" for cmd, info in shell.command_registry.commands.items()
    )
    
    mode_info = (
        f"\n\nCurrent mode: {shell.mode}\n"
        f"- In 'codeact' mode, plain messages are treated as tasks to solve.\n"
        f"- In 'react' mode, plain messages are treated as chat messages."
    )
    
    return help_text + mode_info
