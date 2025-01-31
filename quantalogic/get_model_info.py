from functools import lru_cache

import loguru
from litellm import get_max_tokens as litellm_get_max_tokens

from quantalogic.model_info_list import model_info

DEFAULT_MAX_OUTPUT_TOKENS = 4 * 1024  # Reasonable default for most models
DEFAULT_MAX_INPUT_TOKENS = 32 * 1024  # Reasonable default for most models


def validate_model_name(model_name: str) -> None:
    if not isinstance(model_name, str) or not model_name.strip():
        raise ValueError(f"Invalid model name: {model_name}")


@lru_cache(maxsize=128)
def _call_llm_api(model_name: str) -> int:
    # Rate limit: 10 calls/minute
    return litellm_get_max_tokens(model_name)


def print_model_info():
    for info in model_info.values():
        print(f"\n{info.model_name}:")
        print(f"  Max Input Tokens: {info.max_input_tokens:,}")
        print(f"  Max Output Tokens: {info.max_output_tokens:,}")


def get_max_output_tokens(model_name: str) -> int:
    """Get max output tokens with safe fallback"""
    validate_model_name(model_name)

    if model_name in model_info:
        return model_info[model_name].max_output_tokens

    try:
        return litellm_get_max_tokens(model_name)
    except Exception as e:
        loguru.logger.warning(f"Model {model_name} not found in LiteLLM registry, using default")
        return DEFAULT_MAX_OUTPUT_TOKENS


def get_max_input_tokens(model_name: str) -> int:
    """Get max input tokens with safe fallback"""
    validate_model_name(model_name)

    if model_name in model_info:
        return model_info[model_name].max_input_tokens

    try:
        return litellm_get_max_tokens(model_name)
    except Exception:
        loguru.logger.warning(f"Model {model_name} not found in LiteLLM registry, using default")
        return DEFAULT_MAX_INPUT_TOKENS


def get_max_tokens(model_name: str) -> int:
    """Get total maximum tokens (input + output)"""
    validate_model_name(model_name)

    # Get input and output tokens separately
    input_tokens = get_max_input_tokens(model_name)
    output_tokens = get_max_output_tokens(model_name)

    return input_tokens + output_tokens


if __name__ == "__main__":
    print_model_info()
    print(get_max_input_tokens("gpt-4o-mini"))
    print(get_max_output_tokens("openrouter/openai/gpt-4o-mini"))
