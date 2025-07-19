"""
Basic node decorators module.

This module contains the basic decorators for defining workflow nodes.
"""

import asyncio
import inspect
from typing import Any, Callable

from loguru import logger

from .base import NODE_REGISTRY


def define(func=None, *, name: str | None = None, output: str | None = None):
    """Decorator for defining simple workflow nodes.

    Can be used as `@define` or `@define(name="...", output="...")`.

    Args:
        func: The function to decorate.
        name: Optional name for the node. Defaults to the function name.
        output: Optional context key for the node's result.

    Returns:
        Decorator function wrapping the node logic.
    """
    def decorator(fn: Callable) -> Callable:
        node_name = name or fn.__name__
        
        async def wrapped_func(**kwargs):
            instance = kwargs.pop("instance", None)
            try:
                if asyncio.iscoroutinefunction(fn):
                    if instance:
                        result = await fn(instance, **kwargs)
                    else:
                        result = await fn(**kwargs)
                elif instance:
                    result = fn(instance, **kwargs)
                else:
                    result = fn(**kwargs)
                logger.debug(f"Node {node_name} executed with result: {result}")
                return result
            except Exception as e:
                logger.error(f"Error in node {node_name}: {e}")
                raise

        sig = inspect.signature(fn)
        inputs = [param.name for param in sig.parameters.values() if param.name not in ['self', 'instance']]
        logger.debug(f"Registering node {node_name} with inputs {inputs} and output {output}")
        NODE_REGISTRY.register(node_name, wrapped_func, inputs, output)
        return wrapped_func

    if func is None:
        # Called as @define(name=..., output=...)
        return decorator
    else:
        # Called as @define
        return decorator(func)


def validate_node(output: str):
    """Decorator for nodes that validate inputs and return a string.

    Args:
        output: Context key for the validation result.

    Returns:
        Decorator function wrapping the validation logic.
    """
    def decorator(func: Callable) -> Callable:
        async def wrapped_func(**kwargs):
            kwargs.pop("instance", None)  # Pop instance to avoid passing it to the user function
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
