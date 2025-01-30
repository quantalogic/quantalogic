"""LLM wrapper module for handling LiteLLM operations."""

from typing import Any, Dict, List

import litellm


def generate_completion(**kwargs: Dict[str, Any]) -> Any:
    """Wraps litellm completion with proper type hints."""
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