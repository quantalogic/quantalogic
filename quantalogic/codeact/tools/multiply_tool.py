"""Multiplication tool for the agent."""

from quantalogic.tools import create_tool

from ..utils import log_async_tool


@create_tool
@log_async_tool("Multiplying")
async def multiply_tool(x: int, y: int) -> str:
    """Multiplies two numbers and returns the product as a string.

    Args:
        x (int): First number to multiply.
        y (int): Second number to multiply.

    Returns:
        str: The product of x and y as a string.
    """
    return str(x * y)