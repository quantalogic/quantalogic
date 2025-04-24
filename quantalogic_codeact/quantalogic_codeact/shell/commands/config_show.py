from typing import List

from pydantic import BaseModel

import quantalogic_codeact.cli_commands.config_manager as config_manager


async def config_show(shell, args: List[str]) -> str:
    """Show the current configuration."""
    output = []
    config_file_path = str(config_manager.GLOBAL_CONFIG_PATH)
    output.append(f"[bold yellow]Config file path:[/] {config_file_path}")

    if not isinstance(shell.agent_config, BaseModel):
        return "[bold red]Error: Configuration is not a valid Pydantic model.[/bold red]"

    # Iterate over Pydantic model fields
    for field_name, field_info in shell.agent_config.model_fields.items():
        value = getattr(shell.agent_config, field_name)
        # Handle nested Pydantic models or dataclasses
        if isinstance(value, BaseModel):
            value_str = value.dict()
        elif hasattr(value, '__dict__'):
            value_str = value.__dict__
        else:
            value_str = value
        output.append(f"[bold cyan]{field_name}:[/] [green]{value_str}[/green]")

    return "\n".join(output)