from typing import List


async def agent_command(shell, args: List[str]) -> str:
    """Switch between agents or show details."""
    if not args:
        current = shell.agents[shell.current_agent_name]
        details = f"Current agent: {shell.current_agent_name} (model: {current.agent.model})"
        all_agents = "\n".join(
            f"- {name}: model={state.agent.model}"
            for name, state in shell.agents.items()
        )
        return f"{details}\nAvailable agents:\n{all_agents}"
    name = args[0]
    if name in shell.agents:
        shell.current_agent_name = name
        return f"Switched to agent: {name}"
    return f"Agent '{name}' not found."