from typing import Any, Dict, List, Optional

from loguru import logger

from quantalogic.agent import Agent
from quantalogic.agent_config import (
    DuckDuckGoSearchTool,
    NodeJsTool,
    PythonTool,
    SearchDefinitionNamesTool,
    TaskCompleteTool,
    WikipediaSearchTool,
    create_basic_agent,
    create_full_agent,
    create_interpreter_agent,
)
from quantalogic.coding_agent import create_coding_agent
from quantalogic.memory import AgentMemory
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
        """Register an agent instance with a name."""
        if name in cls._agents:
            raise ValueError(f"Agent with name {name} already exists")
        cls._agents[name] = agent

    @classmethod
    def get_agent(cls, name: str) -> Agent:
        """Retrieve a registered agent by name."""
        return cls._agents[name]

    @classmethod
    def list_agents(cls) -> Dict[str, str]:
        """List all registered agents."""
        return {name: type(agent).__name__ for name, agent in cls._agents.items()}


"""Agent factory module for creating different types of agents."""


def create_agent_for_mode(
    mode: str,
    model_name: str,
    vision_model_name: Optional[str],
    thinking_model_name: Optional[str],
    no_stream: bool = False,
    compact_every_n_iteration: Optional[int] = None,
    max_tokens_working_memory: Optional[int] = None,
    tools: Optional[List[Any]] = None,
    event_emitter: Any = None,
    specific_expertise: str = "",
    memory: AgentMemory | None = None,
    chat_system_prompt: Optional[str] = None,
    tool_mode: Optional[str] = None,
) -> Agent:
    """Create an agent based on the specified mode.

    Args:
        mode: The mode of operation for the agent
        model_name: The name of the language model to use
        vision_model_name: Optional name of the vision model
        thinking_model_name: Optional name for a thinking model
        no_stream: Whether to disable streaming mode
        compact_every_n_iteration: Optional number of iterations before compacting memory
        max_tokens_working_memory: Optional maximum tokens for working memory
        tools: Optional list of tools to include in the agent
        event_emitter: Optional event emitter to use in the agent
        specific_expertise: Optional specific expertise for the agent
        memory: Optional AgentMemory instance to use in the agent
        chat_system_prompt: Optional persona for chat mode
        tool_mode: Optional tool or toolset to prioritize in chat mode
        
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
    logger.debug(f"Using tool_mode: {tool_mode}")

    # Default tools if none provided
    if tools is None:
        tools = [TaskCompleteTool()]

    if mode == "chat":
        logger.debug(f"Creating chat agent with persona: {chat_system_prompt}")
        # Customize tools based on tool_mode
        if tool_mode:
            if tool_mode == "search":
                tools.extend([DuckDuckGoSearchTool(), WikipediaSearchTool()])
            elif tool_mode == "code":
                tools.extend([PythonTool(), NodeJsTool(), SearchDefinitionNamesTool()])
            elif tool_mode in [t.name for t in tools]:  # Specific tool name
                tools = [t for t in tools if t.name == tool_mode or isinstance(t, TaskCompleteTool)]
            else:
                logger.warning(f"Unknown tool mode '{tool_mode}', using default tools")
        agent = Agent(
            model_name=model_name,
            memory=memory if memory else AgentMemory(),
            tools=tools,
            chat_system_prompt=chat_system_prompt,
            tool_mode=tool_mode,
        )
        return agent
    elif mode == "code":
        logger.debug("Creating code agent without basic mode")
        agent = create_coding_agent(
            model_name,
            vision_model_name,
            thinking_model_name,
            basic=False,
            no_stream=no_stream,
            compact_every_n_iteration=compact_every_n_iteration,
            max_tokens_working_memory=max_tokens_working_memory,
        )
        return agent
    elif mode == "code-basic":
        agent = create_coding_agent(
            model_name,
            vision_model_name,
            basic=True,
            no_stream=no_stream,
            compact_every_n_iteration=compact_every_n_iteration,
            max_tokens_working_memory=max_tokens_working_memory,
        )
        return agent
    elif mode == "basic":
        agent = create_basic_agent(
            model_name,
            vision_model_name,
            no_stream=no_stream,
            compact_every_n_iteration=compact_every_n_iteration,
            max_tokens_working_memory=max_tokens_working_memory,
        )
        return agent
    elif mode == "full":
        agent = create_full_agent(
            model_name,
            vision_model_name,
            no_stream=no_stream,
            compact_every_n_iteration=compact_every_n_iteration,
            max_tokens_working_memory=max_tokens_working_memory,
        )
        return agent
    elif mode == "interpreter":
        agent = create_interpreter_agent(
            model_name,
            vision_model_name,
            no_stream=no_stream,
            compact_every_n_iteration=compact_every_n_iteration,
            max_tokens_working_memory=max_tokens_working_memory,
        )
        return agent
    elif mode == "search":
        agent = create_search_agent(
            model_name,
            no_stream=no_stream,
            compact_every_n_iteration=compact_every_n_iteration,
            max_tokens_working_memory=max_tokens_working_memory,
        )
        return agent
    elif mode == "search-full":
        agent = create_search_agent(
            model_name,
            mode_full=True,
            no_stream=no_stream,
            compact_every_n_iteration=compact_every_n_iteration,
            max_tokens_working_memory=max_tokens_working_memory,
        )
        return agent
    else:
        raise ValueError(f"Unknown agent mode: {mode}")