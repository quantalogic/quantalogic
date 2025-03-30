"""Sine calculation tool for the agent."""

import math

from quantalogic.tools import create_tool

from ..utils import log_async_tool


@create_tool
@log_async_tool("Calculating sine")
async def sinus(x: float) -> str:
    """Calculates the sine of a number and returns it as a string.

    Args:
        x (float): The input value in radians.

    Returns:
        str: The sine of x as a string.
    """
    return str(math.sin(x))