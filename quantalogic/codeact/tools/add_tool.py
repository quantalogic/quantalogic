"""Addition tool for the agent."""

from quantalogic.tools import create_tool

from ..utils import log_async_tool


@create_tool
@log_async_tool("Adding")
async def add_tool(a: int, b: int) -> str:
    """Adds two numbers and returns the sum as a string.

    Args:
        a (int): First number to add.
        b (int): Second number to add.

    Returns:
        str: The sum of a and b as a string.
    """
    return str(a + b)