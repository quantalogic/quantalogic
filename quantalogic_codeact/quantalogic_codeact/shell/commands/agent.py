from typing import List


async def agent_command(shell, args: List[str]) -> str:
    """Switch between agents."""
    if not args:
        return f"Current agent: {shell.current_agent_name}\nAvailable agents: {list(shell.agents.keys())}"
    name = args[0]
    if name in shell.agents:
        shell.current_agent_name = name
        return f"Switched to agent: {name}"
    return f"Agent '{name}' not found."