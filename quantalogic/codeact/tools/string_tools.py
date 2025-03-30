"""Math tools toolbox for the agent."""

import math

from quantalogic.tools import create_tool

from ..utils import log_async_tool


@create_tool
@log_async_tool("Calculating sine")
async def sinus(x: float) -> float:
    """Calculates the sine of a number.

    Args:
        x (float): The input value in radians.

    Returns:
        float: The sine of x.
    """
    return math.sin(x)


@create_tool
@log_async_tool("Calculating cosine")
async def cosinus(x: float) -> float:
    """Calculates the cosine of a number.

    Args:
        x (float): The input value in radians.

    Returns:
        float: The cosine of x.
    """
    return math.cos(x)


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


tools = [sinus, cosinus, multiply_tool]