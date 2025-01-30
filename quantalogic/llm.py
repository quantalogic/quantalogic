"""LLM wrapper module for handling LiteLLM operations."""

__all__ = [
    "generate_completion",
    "generate_image",
    "count_tokens",
    "get_model_max_input_tokens",
    "get_model_max_output_tokens",
]

import os
from typing import Any, Dict, List

from litellm import (
    completion,
    image_generation,
    token_counter,
)
from loguru import logger

from quantalogic.get_model_info import (
    get_max_input_tokens,
    get_max_output_tokens,
    model_info,
)


def get_model_info(model_name: str) -> dict | None:
    """Get model information for a given model name."""
    return model_info.get(model_name, None)


def generate_completion(**kwargs: Dict[str, Any]) -> Any:
    """Wraps litellm completion with proper type hints."""
    model = kwargs.get("model", "")
    if model.startswith("dashscope/"):
        # Remove prefix and configure for OpenAI-compatible endpoint
        kwargs["model"] = model.replace("dashscope/", "")
        kwargs["custom_llm_provider"] = "openai"  # Explicitly specify OpenAI provider
        kwargs["base_url"] = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY is not set in the environment variables.")
        kwargs["api_key"] = api_key
    return completion(**kwargs)


def generate_image(**kwargs: Dict[str, Any]) -> Any:
    """Wraps litellm image_generation with proper type hints."""
    return image_generation(**kwargs)


def count_tokens(model: str, messages: List[Dict[str, Any]]) -> int:
    """Wraps litellm token_counter with proper type hints."""
    return token_counter(model=model, messages=messages)


def _get_model_info_impl(model_name: str) -> dict:
    """Get information about the model with prefix fallback logic."""
    original_model = model_name
    tried_models = [model_name]

    while True:
        try:
            logger.debug(f"Attempting to retrieve model info for: {model_name}")
            # Try direct lookup from model_info dictionary first
            if model_name in model_info:
                logger.debug(f"Found model info for {model_name} in model_info")
                return model_info[model_name]

            # Try get_model_info as fallback
            info = get_model_info(model_name)
            if info:
                logger.debug(f"Found model info for {model_name} via get_model_info")
                return info
        except Exception as e:
            logger.debug(f"Failed to get model info for {model_name}: {str(e)}")
            pass

        # Try removing one prefix level
        parts = model_name.split("/")
        if len(parts) <= 1:
            break
        model_name = "/".join(parts[1:])
        tried_models.append(model_name)

    error_msg = f"Could not find model info for {original_model} after trying: {' → '.join(tried_models)}"
    logger.error(error_msg)
    raise ValueError(error_msg)


def get_model_max_input_tokens(model_name: str) -> int | None:
    """Get the maximum number of input tokens for the model."""
    try:
        # First try direct lookup
        max_tokens = get_max_input_tokens(model_name)
        if max_tokens is not None:
            return max_tokens

        # If not found, try getting from model info
        model_info = _get_model_info_impl(model_name)
        max_input = model_info.get("max_input_tokens")
        if max_input is not None:
            return max_input

        # If still not found, log warning and return default
        logger.warning(f"No max input tokens found for {model_name}. Using default.")
        return 8192  # A reasonable default for many models

    except Exception as e:
        logger.error(f"Error getting max input tokens for {model_name}: {e}")
        return None


def get_model_max_output_tokens(model_name: str) -> int | None:
    """Get the maximum number of output tokens for the model."""
    try:
        # First try direct lookup
        max_tokens = get_max_output_tokens(model_name)
        if max_tokens is not None:
            return max_tokens

        # If not found, try getting from model info
        model_info = _get_model_info_impl(model_name)
        max_output = model_info.get("max_output_tokens")
        if max_output is not None:
            return max_output

        # If still not found, log warning and return default
        logger.warning(f"No max output tokens found for {model_name}. Using default.")
        return 4096  # A reasonable default for many models

    except Exception as e:
        logger.error(f"Error getting max output tokens for {model_name}: {e}")
        return None