"""
Template nodes module.

This module contains decorators for template-based workflow nodes.
"""

import asyncio
import inspect
from typing import Callable

from loguru import logger

from ..template import TemplateEngine
from .base import NODE_REGISTRY


def template_node(
    output: str,
    template: str = "",
    template_file: str | None = None,
):
    """Decorator for creating nodes that apply a Jinja2 template to inputs.

    Args:
        output: Context key for the rendered result.
        template: Inline Jinja2 template string.
        template_file: Path to a template file (overrides template).

    Returns:
        Decorator function wrapping the template logic.
    """
    def decorator(func: Callable) -> Callable:
        async def wrapped_func(**func_kwargs):
            template_to_use = func_kwargs.pop("template", template)
            template_file_to_use = func_kwargs.pop("template_file", template_file)

            sig = inspect.signature(func)
            expected_params = [p.name for p in sig.parameters.values() if p.name != 'rendered_content']
            template_vars = {k: v for k, v in func_kwargs.items() if k in expected_params}
            rendered_content = TemplateEngine.render_template(template_to_use, template_file_to_use, template_vars)

            filtered_kwargs = {k: v for k, v in func_kwargs.items() if k in expected_params}

            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(rendered_content=rendered_content, **filtered_kwargs)
                else:
                    result = func(rendered_content=rendered_content, **filtered_kwargs)
                logger.debug(f"Template node {func.__name__} rendered: {rendered_content[:50]}...")
                return result
            except Exception as e:
                logger.error(f"Error in template node {func.__name__}: {e}")
                raise
        sig = inspect.signature(func)
        inputs = [param.name for param in sig.parameters.values()]
        if 'rendered_content' not in inputs:
            inputs.insert(0, 'rendered_content')
        logger.debug(f"Registering node {func.__name__} with inputs {inputs} and output {output}")
        NODE_REGISTRY.register(func.__name__, wrapped_func, inputs, output)
        return wrapped_func
    return decorator
