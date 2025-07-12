"""
Node system initialization.

This module maintains the original Nodes API while using modular components.
"""

import inspect
from typing import Any, Callable, Dict, Type, Union

import instructor
from litellm import acompletion
from loguru import logger
from pydantic import BaseModel, ValidationError

from ..template import TemplateEngine
from .base import NODE_REGISTRY
from .decorators import define as _define, transform_node as _transform_node, validate_node as _validate_node
from .template_nodes import template_node as _template_node


class Nodes:
    """
    Node decorator class providing all the node creation functionality.
    
    This class maintains 100% API compatibility with the original implementation
    while using modular components underneath.
    """
    
    # For backward compatibility, expose the registry as a class attribute
    NODE_REGISTRY = NODE_REGISTRY._registry
    
    @classmethod
    def define(cls, output: str | None = None):
        """Decorator for defining simple workflow nodes."""
        return _define(output)
    
    @classmethod
    def validate_node(cls, output: str):
        """Decorator for nodes that validate inputs and return a string."""
        return _validate_node(output)
    
    @classmethod
    def transform_node(cls, output: str, transformer: Callable[[Any], Any]):
        """Decorator for nodes that transform their inputs."""
        return _transform_node(output, transformer)
    
    @classmethod
    def template_node(cls, output: str, template: str = "", template_file: str | None = None):
        """Decorator for creating nodes that apply a Jinja2 template to inputs."""
        return _template_node(output, template, template_file)
    
    @staticmethod
    def _load_prompt_from_file(prompt_file: str, context: Dict[str, Any]) -> str:
        """Load and render a Jinja2 template from an external file."""
        return TemplateEngine.load_prompt_from_file(prompt_file, context)
    
    @staticmethod  
    def _render_template(template: str, template_file: str | None, context: Dict[str, Any]) -> str:
        """Render a Jinja2 template from either a string or an external file."""
        return TemplateEngine.render_template(template, template_file, context)
    
    @classmethod
    def llm_node(
        cls,
        system_prompt: str = "",
        system_prompt_file: str | None = None,
        output: str = "",
        prompt_template: str = "",
        prompt_file: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        top_p: float = 1.0,
        presence_penalty: float = 0.0,
        frequency_penalty: float = 0.0,
        model: Union[Callable[[Dict[str, Any]], str], str] = lambda ctx: "gpt-3.5-turbo",
        **kwargs,
    ):
        """Decorator for creating LLM nodes with plain text output, supporting dynamic parameters."""
        def decorator(func: Callable) -> Callable:
            # Store all decorator parameters in a config dictionary
            config = {
                "system_prompt": system_prompt,
                "system_prompt_file": system_prompt_file,
                "prompt_template": prompt_template,
                "prompt_file": prompt_file,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
                "presence_penalty": presence_penalty,
                "frequency_penalty": frequency_penalty,
                "model": model,
                **kwargs,
            }

            async def wrapped_func(**func_kwargs):
                # Use func_kwargs to override config values if provided, otherwise use config defaults
                system_prompt_to_use = func_kwargs.pop("system_prompt", config["system_prompt"])
                system_prompt_file_to_use = func_kwargs.pop("system_prompt_file", config["system_prompt_file"])
                prompt_template_to_use = func_kwargs.pop("prompt_template", config["prompt_template"])
                prompt_file_to_use = func_kwargs.pop("prompt_file", config["prompt_file"])
                temperature_to_use = func_kwargs.pop("temperature", config["temperature"])
                max_tokens_to_use = func_kwargs.pop("max_tokens", config["max_tokens"])
                top_p_to_use = func_kwargs.pop("top_p", config["top_p"])
                presence_penalty_to_use = func_kwargs.pop("presence_penalty", config["presence_penalty"])
                frequency_penalty_to_use = func_kwargs.pop("frequency_penalty", config["frequency_penalty"])
                model_to_use = func_kwargs.pop("model", config["model"])

                # Handle callable model parameter
                if callable(model_to_use):
                    model_to_use = model_to_use(func_kwargs)

                # Load system prompt from file if specified
                if system_prompt_file_to_use:
                    system_content = cls._load_prompt_from_file(system_prompt_file_to_use, func_kwargs)
                else:
                    system_content = system_prompt_to_use

                # Prepare template variables and render prompt
                sig = inspect.signature(func)
                template_vars = {k: v for k, v in func_kwargs.items() if k in sig.parameters}
                prompt = cls._render_template(prompt_template_to_use, prompt_file_to_use, template_vars)
                messages = [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": prompt},
                ]

                # Logging for debugging
                truncated_prompt = prompt[:200] + "..." if len(prompt) > 200 else prompt
                logger.info(f"LLM node {func.__name__} using model: {model_to_use}")
                logger.debug(f"System prompt: {system_content[:100]}...")
                logger.debug(f"User prompt preview: {truncated_prompt}")

                # Call the acompletion function with the resolved model
                try:
                    response = await acompletion(
                        model=model_to_use,
                        messages=messages,
                        temperature=temperature_to_use,
                        max_tokens=max_tokens_to_use,
                        top_p=top_p_to_use,
                        presence_penalty=presence_penalty_to_use,
                        frequency_penalty=frequency_penalty_to_use,
                        drop_params=True,
                        **kwargs,
                    )
                    content = response.choices[0].message.content.strip()
                    wrapped_func.usage = {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                        "cost": getattr(response, "cost", None),
                    }
                    logger.debug(f"LLM output from {func.__name__}: {content[:50]}...")
                    return content
                except Exception as e:
                    logger.error(f"Error in LLM node {func.__name__}: {e}")
                    raise

            # Register the node with its inputs and output
            sig = inspect.signature(func)
            inputs = [param.name for param in sig.parameters.values()]
            logger.debug(f"Registering node {func.__name__} with inputs {inputs} and output {output}")
            NODE_REGISTRY.register(func.__name__, wrapped_func, inputs, output)
            return wrapped_func
        return decorator
    
    @classmethod
    def structured_llm_node(
        cls,
        system_prompt: str = "",
        system_prompt_file: str | None = None,
        output: str = "",
        response_model: Type[BaseModel] = None,
        prompt_template: str = "",
        prompt_file: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        top_p: float = 1.0,
        presence_penalty: float = 0.0,
        frequency_penalty: float = 0.0,
        model: Union[Callable[[Dict[str, Any]], str], str] = lambda ctx: "gpt-3.5-turbo",
        **kwargs,
    ):
        """Decorator for creating LLM nodes with structured output, supporting dynamic parameters."""
        try:
            client = instructor.from_litellm(acompletion)
        except ImportError:
            logger.error("Instructor not installed. Install with 'pip install instructor[litellm]'")
            raise ImportError("Instructor is required for structured_llm_node")

        def decorator(func: Callable) -> Callable:
            # Store all decorator parameters in a config dictionary
            config = {
                "system_prompt": system_prompt,
                "system_prompt_file": system_prompt_file,
                "prompt_template": prompt_template,
                "prompt_file": prompt_file,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
                "presence_penalty": presence_penalty,
                "frequency_penalty": frequency_penalty,
                "model": model,
                **kwargs,
            }

            async def wrapped_func(**func_kwargs):
                # Resolve parameters, prioritizing func_kwargs over config defaults
                system_prompt_to_use = func_kwargs.pop("system_prompt", config["system_prompt"])
                system_prompt_file_to_use = func_kwargs.pop("system_prompt_file", config["system_prompt_file"])
                prompt_template_to_use = func_kwargs.pop("prompt_template", config["prompt_template"])
                prompt_file_to_use = func_kwargs.pop("prompt_file", config["prompt_file"])
                temperature_to_use = func_kwargs.pop("temperature", config["temperature"])
                max_tokens_to_use = func_kwargs.pop("max_tokens", config["max_tokens"])
                top_p_to_use = func_kwargs.pop("top_p", config["top_p"])
                presence_penalty_to_use = func_kwargs.pop("presence_penalty", config["presence_penalty"])
                frequency_penalty_to_use = func_kwargs.pop("frequency_penalty", config["frequency_penalty"])
                model_to_use = func_kwargs.pop("model", config["model"])

                # Handle callable model parameter
                if callable(model_to_use):
                    model_to_use = model_to_use(func_kwargs)

                # Load system prompt from file if specified
                if system_prompt_file_to_use:
                    system_content = cls._load_prompt_from_file(system_prompt_file_to_use, func_kwargs)
                else:
                    system_content = system_prompt_to_use

                # Render prompt using template variables
                sig = inspect.signature(func)
                template_vars = {k: v for k, v in func_kwargs.items() if k in sig.parameters}
                prompt = cls._render_template(prompt_template_to_use, prompt_file_to_use, template_vars)
                messages = [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": prompt},
                ]

                # Logging for debugging
                truncated_prompt = prompt[:200] + "..." if len(prompt) > 200 else prompt
                logger.info(f"Structured LLM node {func.__name__} using model: {model_to_use}")
                logger.debug(f"System prompt: {system_content[:100]}...")
                logger.debug(f"User prompt preview: {truncated_prompt}")
                logger.debug(f"Expected response model: {response_model.__name__}")

                # Generate structured response
                try:
                    structured_response, raw_response = await client.chat.completions.create_with_completion(
                        model=model_to_use,
                        messages=messages,
                        response_model=response_model,
                        temperature=temperature_to_use,
                        max_tokens=max_tokens_to_use,
                        top_p=top_p_to_use,
                        presence_penalty=presence_penalty_to_use,
                        frequency_penalty=frequency_penalty_to_use,
                        drop_params=True,
                        **kwargs,
                    )
                    wrapped_func.usage = {
                        "prompt_tokens": raw_response.usage.prompt_tokens,
                        "completion_tokens": raw_response.usage.completion_tokens,
                        "total_tokens": raw_response.usage.total_tokens,
                        "cost": getattr(raw_response, "cost", None),
                    }
                    logger.debug(f"Structured output from {func.__name__}: {structured_response}")
                    return structured_response
                except ValidationError as e:
                    logger.error(f"Validation error in {func.__name__}: {e}")
                    raise
                except Exception as e:
                    logger.error(f"Error in structured LLM node {func.__name__}: {e}")
                    raise

            # Register the node
            sig = inspect.signature(func)
            inputs = [param.name for param in sig.parameters.values()]
            logger.debug(f"Registering node {func.__name__} with inputs {inputs} and output {output}")
            NODE_REGISTRY.register(func.__name__, wrapped_func, inputs, output)
            return wrapped_func
        return decorator
