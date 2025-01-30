"""LLM wrapper module for handling LiteLLM operations."""

import os
from typing import Any, Dict, List

import litellm


def generate_completion(**kwargs: Dict[str, Any]) -> Any:
    """Wraps litellm completion with proper type hints."""
    model = kwargs.get('model', '')
    if model.startswith('dashscope/'):
        # Remove prefix and configure for OpenAI-compatible endpoint
        kwargs['model'] = model.replace('dashscope/', '')
        kwargs['custom_llm_provider'] = 'openai'  # Explicitly specify OpenAI provider
        kwargs['base_url'] = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY is not set in the environment variables.")
        kwargs['api_key'] = api_key
    return litellm.completion(**kwargs)

def generate_image(**kwargs: Dict[str, Any]) -> Any:
    """Wraps litellm image_generation with proper type hints."""
    return litellm.image_generation(**kwargs)

def count_tokens(model: str, messages: List[Dict[str, Any]]) -> int:
    """Wraps litellm token_counter with proper type hints."""
    return litellm.token_counter(model=model, messages=messages)

__all__ = [
    "generate_completion",
    "generate_image", 
    "count_tokens"
]