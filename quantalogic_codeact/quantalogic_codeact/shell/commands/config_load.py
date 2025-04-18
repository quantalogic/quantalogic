from typing import List

import yaml
from loguru import logger

from ...codeact.agent import Agent, AgentConfig
from ..agent_state import AgentState


async def config_load(shell, args: List[str]) -> str:
    """Load a configuration from a file and update the agent."""
    if not args:
        return "Please provide a filename. Usage: /config load [filename]"
    filename = args[0]
    try:
        with open(filename) as f:
            new_config_dict = yaml.safe_load(f) or {}
        new_config = AgentConfig(**new_config_dict)
        # Create a new agent with the loaded configuration
        new_agent = Agent(config=new_config)
        new_agent.add_observer(shell._stream_token_observer, ["StreamToken"])
        # Update the current agent in the agents dictionary
        shell.agents[shell.current_agent_name] = AgentState(agent=new_agent)
        logger.info(f"Configuration loaded from {filename}")
        return f"Configuration loaded from {filename}"
    except Exception as e:
        logger.error(f"Error loading configuration from {filename}: {e}")
        return f"Error loading configuration: {e}"