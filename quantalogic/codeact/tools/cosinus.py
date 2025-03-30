"""Cosine calculation tool for the agent."""

import math

from quantalogic.tools import create_tool

from ..utils import log_async_tool


@create_tool
@log_async_tool("Calculating cosine")
async def cosinus(x: float) -> str:
    """Calculates the cosine of a number and returns it as a string.

    Args:
        x (float): The input value in radians.

    Returns:
        str: The cosine of x as a string.
    """
    return str(math.cos(x))