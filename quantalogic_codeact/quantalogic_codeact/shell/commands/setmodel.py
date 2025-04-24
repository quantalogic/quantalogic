from typing import List

from ...codeact.agent import Agent
from ..agent_state import AgentState


async def setmodel_command(shell, args: List[str]) -> str:
    """Set the model by updating the agent config and switching to a new agent: /setmodel <model_name>
    
    Args:
        shell: The Shell instance.
        args: List of arguments, expecting a single model name (e.g., 'deepseek/deepseek-chat').
    
    Returns:
        str: A message indicating the result of the operation.
    """
    if not args:
        return "Please provide a model name (e.g., 'deepseek/deepseek-chat')."
    new_model = args[0]
    # Update the centralized agent_config
    shell.agent_config.model = new_model
    # Instantiate a new agent with the updated config
    new_agent = Agent(config=shell.agent_config)
    # Add the stream token observer to maintain streaming consistency
    new_agent.add_observer(shell._stream_token_observer, ["StreamToken"])
    # Generate a unique agent name based on the model
    base_name = f"agent_{new_model.replace('/', '_')}"
    name = base_name
    index = 1
    while name in shell.agents:
        name = f"{base_name}_{index}"
        index += 1
    # Add the new agent to the agents dictionary and switch to it
    shell.agents[name] = AgentState(agent=new_agent)
    shell.current_agent_name = name
    return f"Created and switched to new agent: {name} with model {new_model}"