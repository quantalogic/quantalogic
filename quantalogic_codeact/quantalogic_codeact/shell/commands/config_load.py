from typing import List

import typer
from loguru import logger

from quantalogic_codeact.cli_commands.config_manager import GLOBAL_CONFIG_PATH
from quantalogic_codeact.codeact.agent import AgentConfig

from ...codeact.agent import Agent
from ..agent_state import AgentState

app = typer.Typer()

@app.command()
def config_load(shell, args: List[str]) -> str:
    """Load a configuration from a file into the default config location."""
    try:
        path = args[0] if args else str(GLOBAL_CONFIG_PATH)
        shell.agent_config = AgentConfig.load_from_file(path)
        new_agent = Agent(config=shell.agent_config)
        new_agent.add_observer(shell._stream_token_observer, ["StreamToken"])
        shell.agents[shell.current_agent_name] = AgentState(agent=new_agent)
        logger.info(f"Configuration loaded from {path}")
        typer.echo(f"Configuration loaded from {path}")
        return f"Configuration loaded from {path}"
    except Exception as e:
        logger.error(f"Error loading configuration from {path}: {e}")
        typer.echo(f"Error loading configuration: {e}")
        raise typer.Exit(code=1)