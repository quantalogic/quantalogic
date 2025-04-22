from typing import List


async def set_temperature_command(shell, args: List[str]) -> str:
    """Set or display the temperature for the current agent: /set temperature <value>
    
    Args:
        shell: The Shell instance.
        args: List containing the temperature value (optional).
    
    Returns:
        str: A message indicating the current temperature or the result of setting it.
    """
    if not args:
        return f"Current temperature: {shell.current_agent.react_agent.temperature}"
    try:
        value = float(args[0])
        if not 0 <= value <= 1:
            return "Temperature must be between 0 and 1."
        shell.current_agent.react_agent.set_temperature(value)
        return f"Temperature set to {value}"
    except ValueError:
        return "Invalid temperature value. Please provide a float between 0 and 1."