from dataclasses import fields
from pathlib import Path
from typing import List

import yaml
from loguru import logger

import quantalogic_codeact.codeact.cli_commands.config_manager as config_manager

from ...codeact.agent import Agent, AgentConfig
from ..agent_state import AgentState


async def config_load(shell, args: List[str]) -> str:
    """Load a configuration from a file and update the agent."""
    # Determine config path: use provided filename or default global config
    if not args:
        path = config_manager.GLOBAL_CONFIG_PATH.expanduser().resolve()
    else:
        path = Path(args[0]).expanduser().resolve()
    try:
        with open(path) as f:
            new_config_dict = yaml.safe_load(f) or {}
        # Filter out unsupported keys based on AgentConfig schema
        valid_keys = {f.name for f in fields(AgentConfig)}
        for key in list(new_config_dict):
            if key not in valid_keys:
                logger.warning(f"Unknown config key '{key}' ignored.")
                new_config_dict.pop(key)
        new_config = AgentConfig(**new_config_dict)
        # Create a new agent with the loaded configuration
        new_agent = Agent(config=new_config)
        new_agent.add_observer(shell._stream_token_observer, ["StreamToken"])
        # Update the current agent in the agents dictionary
        shell.agents[shell.current_agent_name] = AgentState(agent=new_agent)
        # Track this path for future operations
        config_manager.GLOBAL_CONFIG_PATH = path
        config_manager.PROJECT_CONFIG_PATH = path
        logger.info(f"Configuration loaded from {path}")
        return f"Configuration loaded from {path}"
    except Exception as e:
        logger.error(f"Error loading configuration from {path}: {e}")
        return f"Error loading configuration: {e}"