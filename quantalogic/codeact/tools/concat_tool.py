"""String concatenation tool for the agent."""

from quantalogic.tools import create_tool

from ..utils import log_async_tool


@create_tool
@log_async_tool("Concatenating")
async def concat_tool(s1: str, s2: str) -> str:
    """Concatenates two strings and returns the result.

    Args:
        s1 (str): First string to concatenate.
        s2 (str): Second string to concatenate.

    Returns:
        str: The concatenated string.
    """
    return s1 + s2