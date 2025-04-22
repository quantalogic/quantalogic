from typing import List

from rich.text import Text


async def help_command(shell, args: List[str]) -> Text:
    """Display help text, including mode information."""
    if args:
        command = args[0]
        if command in shell.command_registry.commands:
            return Text(shell.command_registry.commands[command]["help"])
        return Text(f"Command '/{command}' not found.", style="red")
    
    text = Text()
    text.append("Available commands:\n", style="bold")
    for cmd, info in shell.command_registry.commands.items():
        text.append(f"- /{cmd}: ", style="cyan")
        text.append(info["help"] + "\n")
    
    text.append("\nAdditional commands:\n", style="bold")
    text.append("- /set: Set a config field: /set <field> <value>\n")
    
    text.append("\nCurrent mode: ", style="bold")
    text.append(shell.state.mode, style="green")
    mode_info = (
        "\n- In 'codeact' mode, plain messages are treated as tasks to solve.\n"
        "- In 'chat' mode, plain messages are treated as chat messages."
    )
    text.append(mode_info)
    
    return text