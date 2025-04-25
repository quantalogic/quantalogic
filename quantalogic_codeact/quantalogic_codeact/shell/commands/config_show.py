from typing import List

import yaml
from pydantic import BaseModel
from rich.syntax import Syntax

import quantalogic_codeact.cli_commands.config_manager as config_manager


async def config_show(shell, args: List[str]) -> str:
    """Show the current configuration as YAML."""
    config_file_path = str(config_manager.GLOBAL_CONFIG_PATH)

    if not isinstance(shell.agent_config, BaseModel):
        return "[bold red]Error: Configuration is not a valid Pydantic model.[/bold red]"

    # Convert config to dict
    if hasattr(shell.agent_config, "model_dump"):
        config_dict = shell.agent_config.model_dump()
    elif hasattr(shell.agent_config, "dict"):
        config_dict = shell.agent_config.dict()
    else:
        config_dict = dict(shell.agent_config)

    # Include config file path
    config_dict["config_file_path"] = config_file_path

    # Dump to YAML
    yaml_str = yaml.safe_dump(config_dict, sort_keys=False)

    # Render with syntax highlighting
    syntax = Syntax(yaml_str, "yaml", theme="monokai", line_numbers=False)
    return syntax