import ast
import inspect
from functools import wraps
from typing import Callable, List, Union

from loguru import logger

from quantalogic.tools import Tool, create_tool


def log_async_tool(verb: str):
    """Decorator factory for consistent async tool logging."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            logger.info(f"Starting tool: {func.__name__}")
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            logger.info(f"{verb} {', '.join(f'{k}={v}' for k, v in bound_args.arguments.items())}")
            result = await func(*args, **kwargs)
            logger.info(f"Finished tool: {func.__name__}")
            return result
        return wrapper
    return decorator

def log_tool_method(func: Callable) -> Callable:
    """Decorator for logging Tool class methods."""
    @wraps(func)
    async def wrapper(self, **kwargs):
        logger.info(f"Starting tool: {self.name}")
        try:
            result = await func(self, **kwargs)
            logger.info(f"Finished tool: {self.name}")
            return result
        except Exception as e:
            logger.error(f"Tool {self.name} failed: {e}")
            raise
    return wrapper

def validate_code(code: str) -> bool:
    """Check if code has an async main() function."""
    try:
        tree = ast.parse(code)
        return any(isinstance(node, ast.AsyncFunctionDef) and node.name == "main" 
                  for node in ast.walk(tree))
    except SyntaxError:
        return False

def process_tools(tools: List[Union[Tool, Callable]]) -> List[Tool]:
    """Convert a list of tools or callables into Tool instances."""
    processed_tools: List[Tool] = []
    for tool in tools:
        if isinstance(tool, Tool) or (
            hasattr(tool, 'name') and 
            hasattr(tool, 'description') and 
            hasattr(tool, 'async_execute')
        ):
            processed_tools.append(tool)
        elif callable(tool):
            if not inspect.iscoroutinefunction(tool):
                tool_name = getattr(tool, 'name', getattr(tool, '__name__', str(tool)))
                raise ValueError(f"Callable '{tool_name}' must be an async function to be used as a tool.")
            processed_tools.append(create_tool(tool))
        else:
            raise ValueError(f"Invalid item type: {type(tool)}. Expected Tool, tool-like instance, or async function.")
    return processed_tools