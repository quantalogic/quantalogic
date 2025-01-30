from typing import Dict, Optional

from loguru import logger

from quantalogic.agent import Agent
from quantalogic.agent_config import (
    create_basic_agent,
    create_full_agent,
    create_interpreter_agent,
)
from quantalogic.coding_agent import create_coding_agent
from quantalogic.search_agent import create_search_agent  # noqa: E402


class AgentRegistry:
    """Registry for managing agent instances by name."""
    
    _instance = None
    _agents: Dict[str, Agent] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register_agent(cls, name: str, agent: Agent) -> None:
        """Register an agent instance with a name.
        
        Args:
            name: Unique name for the agent
            agent: Agent instance to register
        """
        if name in cls._agents:
            raise ValueError(f"Agent with name {name} already exists")
        cls._agents[name] = agent

    @classmethod
    def get_agent(cls, name: str) -> Agent:
        """Retrieve a registered agent by name.
        
        Args:
            name: Name of the agent to retrieve
            
        Returns:
            Registered Agent instance
            
        Raises:
            KeyError: If no agent with that name exists
        """
        return cls._agents[name]

    @classmethod
    def list_agents(cls) -> Dict[str, str]:
        """List all registered agents.
        
        Returns:
            Dictionary mapping agent names to their types
        """
        return {name: type(agent).__name__ for name, agent in cls._agents.items()}

"""Agent factory module for creating different types of agents."""


def create_agent_for_mode(
    mode: str,
    model_name: str,
    vision_model_name: Optional[str],
    no_stream: bool = False,
    compact_every_n_iteration: Optional[int] = None,
    max_tokens_working_memory: Optional[int] = None
) -> Agent:
    """Create an agent based on the specified mode.
    
    Args:
        mode: The mode of operation for the agent
        model_name: The name of the language model to use
        vision_model_name: Optional name of the vision model
        no_stream: Whether to disable streaming mode
        compact_every_n_iteration: Optional number of iterations before compacting memory
        max_tokens_working_memory: Optional maximum tokens for working memory
        
    Returns:
        Agent: The created agent instance
        
    Raises:
        ValueError: If an unknown agent mode is specified
    """
    logger.debug(f"Creating agent for mode: {mode} with model: {model_name}")
    logger.debug(f"Using vision model: {vision_model_name}")
    logger.debug(f"Using no_stream: {no_stream}")
    logger.debug(f"Using compact_every_n_iteration: {compact_every_n_iteration}")
    logger.debug(f"Using max_tokens_working_memory: {max_tokens_working_memory}")

    if mode == "code":
        logger.debug("Creating code agent without basic mode")
        agent = create_coding_agent(
            model_name,
            vision_model_name,
            basic=False,
            no_stream=no_stream,
            compact_every_n_iteration=compact_every_n_iteration,
            max_tokens_working_memory=max_tokens_working_memory
        )
        return agent
    if mode == "code-basic":
        agent = create_coding_agent(
            model_name,
            vision_model_name,
            basic=True,
            no_stream=no_stream,
            compact_every_n_iteration=compact_every_n_iteration,
            max_tokens_working_memory=max_tokens_working_memory
        )
        return agent
    elif mode == "basic":
        agent = create_basic_agent(
            model_name,
            vision_model_name,
            no_stream=no_stream,
            compact_every_n_iteration=compact_every_n_iteration,
            max_tokens_working_memory=max_tokens_working_memory
        )
        return agent
    elif mode == "full":
        agent = create_full_agent(
            model_name,
            vision_model_name,
            no_stream=no_stream,
            compact_every_n_iteration=compact_every_n_iteration,
            max_tokens_working_memory=max_tokens_working_memory
        )
        return agent
    elif mode == "interpreter":
        agent = create_interpreter_agent(
            model_name,
            vision_model_name,
            no_stream=no_stream,
            compact_every_n_iteration=compact_every_n_iteration,
            max_tokens_working_memory=max_tokens_working_memory
        )
        return agent
    elif mode == "search":
        agent = create_search_agent(
            model_name,
            no_stream=no_stream,
            compact_every_n_iteration=compact_every_n_iteration,
            max_tokens_working_memory=max_tokens_working_memory
        )
        return agent
    if mode == "search-full":
        agent = create_search_agent(
            model_name,
            mode_full=True,
            no_stream=no_stream,
            compact_every_n_iteration=compact_every_n_iteration,
            max_tokens_working_memory=max_tokens_working_memory
        )
        return agent
    else:
        raise ValueError(f"Unknown agent mode: {mode}")
