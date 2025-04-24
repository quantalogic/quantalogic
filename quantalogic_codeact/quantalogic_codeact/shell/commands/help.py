from typing import List


async def help_command(shell, args: List[str]) -> str:
    """Show help for commands: /help [command]"""
    if not args:
        # General help: list all commands
        output = ["[bold green]Available commands:[/bold green]"]
        for cmd, info in sorted(shell.command_registry.commands.items()):
            output.append(f"[bold cyan]/{cmd}[/bold cyan] - {info['help']}")
        output.append("\n[bold yellow]Type /help <command>[/bold yellow] for detailed help on a specific command.")
        return "\n".join(output)
    
    cmd = args[0].lower()
    if cmd in shell.command_registry.commands:
        info = shell.command_registry.commands[cmd]
        detailed_help = f"[bold cyan]Command:[/bold cyan] [bold]/{cmd}[/bold]\n[green]{info['help']}[/green]"
        if info["args"]:
            detailed_help += f"\n[bold yellow]Possible arguments:[/bold yellow] [italic]{', '.join(info['args'])}[/italic]"
        return detailed_help
    else:
        return f"[bold red]No such command: {cmd}![/bold red] Try [bold yellow]/help[/bold yellow] to see all commands."