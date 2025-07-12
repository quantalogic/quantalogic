"""
Basic node decorators module.

This module contains the basic decorators for defining workflow nodes.
"""

import asyncio
import inspect
from typing import Any, Callable

from loguru import logger

from .base import NODE_REGISTRY


def define(output: str | None = None):
    """Decorator for defining simple workflow nodes.

    Args:
        output: Optional context key for the node's result.

    Returns:
        Decorator function wrapping the node logic.
    """
    def decorator(func: Callable) -> Callable:
        async def wrapped_func(**kwargs):
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(**kwargs)
                else:
                    result = func(**kwargs)
                logger.debug(f"Node {func.__name__} executed with result: {result}")
                return result
            except Exception as e:
                logger.error(f"Error in node {func.__name__}: {e}")
                raise
        sig = inspect.signature(func)
        inputs = [param.name for param in sig.parameters.values()]
        logger.debug(f"Registering node {func.__name__} with inputs {inputs} and output {output}")
        NODE_REGISTRY.register(func.__name__, wrapped_func, inputs, output)
        return wrapped_func
    return decorator


def validate_node(output: str):
    """Decorator for nodes that validate inputs and return a string.

    Args:
        output: Context key for the validation result.

    Returns:
        Decorator function wrapping the validation logic.
    """
    def decorator(func: Callable) -> Callable:
        async def wrapped_func(**kwargs):
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(**kwargs)
                else:
                    result = func(**kwargs)
                if not isinstance(result, str):
                    raise ValueError(f"Validation node {func.__name__} must return a string")
                logger.info(f"Validation result from {func.__name__}: {result}")
                return result
            except Exception as e:
                logger.error(f"Validation error in {func.__name__}: {e}")
                raise
        sig = inspect.signature(func)
        inputs = [param.name for param in sig.parameters.values()]
        logger.debug(f"Registering node {func.__name__} with inputs {inputs} and output {output}")
        NODE_REGISTRY.register(func.__name__, wrapped_func, inputs, output)
        return wrapped_func
    return decorator


def transform_node(output: str, transformer: Callable[[Any], Any]):
    """Decorator for nodes that transform their inputs.

    Args:
        output: Context key for the transformed result.
        transformer: Callable to transform the input.

    Returns:
        Decorator function wrapping the transformation logic.
    """
    def decorator(func: Callable) -> Callable:
        async def wrapped_func(**kwargs):
            try:
                input_key = list(kwargs.keys())[0] if kwargs else None
                if input_key:
                    transformed_input = transformer(kwargs[input_key])
                    kwargs[input_key] = transformed_input
                if asyncio.iscoroutinefunction(func):
                    result = await func(**kwargs)
                else:
                    result = func(**kwargs)
                logger.debug(f"Transformed node {func.__name__} executed with result: {result}")
                return result
            except Exception as e:
                logger.error(f"Error in transform node {func.__name__}: {e}")
                raise
        sig = inspect.signature(func)
        inputs = [param.name for param in sig.parameters.values()]
        logger.debug(f"Registering node {func.__name__} with inputs {inputs} and output {output}")
        NODE_REGISTRY.register(func.__name__, wrapped_func, inputs, output)
        return wrapped_func
    return decorator
