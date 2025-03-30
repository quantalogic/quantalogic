"""Cosine calculation tool for the agent."""

import math

from quantalogic.tools import create_tool

from ..utils import log_async_tool


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