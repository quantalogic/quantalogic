from typing import List

from rich.panel import Panel


async def help_command(shell, args: List[str]) -> str:
    """Show help for commands: /help [command]"""
    if not args:
        # General help: list all commands
        output = ["Available commands:"]
        for cmd, info in sorted(shell.command_registry.commands.items()):
            output.append(f"/{cmd}: {info['help']}")
        output.append("\nType /help <command> for detailed help on a specific command.")
        return "\n".join(output)
    
    cmd = args[0].lower()
    if cmd in shell.command_registry.commands:
        info = shell.command_registry.commands[cmd]
        detailed_help = f"Command: /{cmd}\n{info['help']}"
        if info["args"]:
            detailed_help += f"\nPossible arguments: {', '.join(info['args'])}"
        return detailed_help
    else:
        return f"No such command: {cmd}. Try /help to see all commands."