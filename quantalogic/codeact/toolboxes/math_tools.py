"""Simple math toolbox for the Quantalogic Agent."""

from quantalogic.tools import create_tool


@create_tool
async def add_numbers(a: float, b: float) -> float:
    """Adds two numbers and returns the sum.

    Args:
        a (float): First number to add.
        b (float): Second number to add.

    Returns:
        float: The sum of a and b.
    """
    return a + b


@create_tool
async def subtract_numbers(a: float, b: float) -> float:
    """Subtracts the second number from the first and returns the difference.

    Args:
        a (float): Number to subtract from.
        b (float): Number to subtract.

    Returns:
        float: The difference of a minus b.
    """
    return a - b


@create_tool
async def multiply_numbers(a: float, b: float) -> float:
    """Multiplies two numbers and returns the product.

    Args:
        a (float): First number to multiply.
        b (float): Second number to multiply.

    Returns:
        float: The product of a and b.
    """
    return a * b


@create_tool
async def divide_numbers(a: float, b: float) -> float:
    """Divides the first number by the second and returns the quotient.

    Args:
        a (float): Number to divide.
        b (float): Number to divide by (must not be zero).

    Returns:
        float: The quotient of a divided by b.

    Raises:
        ValueError: If b is zero.
    """
    if b == 0:
        raise ValueError("Division by zero is not allowed")
    return a / b