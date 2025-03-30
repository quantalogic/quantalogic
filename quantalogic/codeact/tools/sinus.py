"""Sine calculation tool for the agent."""

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