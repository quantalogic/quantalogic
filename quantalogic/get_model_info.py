import loguru

from quantalogic.model_info_list import model_info
from quantalogic.model_info_litellm import litellm_get_model_max_input_tokens, litellm_get_model_max_output_tokens
from quantalogic.utils.lm_studio_model_info import get_model_list

DEFAULT_MAX_OUTPUT_TOKENS = 4 * 1024  # Reasonable default for most models
DEFAULT_MAX_INPUT_TOKENS = 32 * 1024  # Reasonable default for most models


def validate_model_name(model_name: str) -> None:
    if not isinstance(model_name, str) or not model_name.strip():
        raise ValueError(f"Invalid model name: {model_name}")


def print_model_info():
    for info in model_info.values():
        print(f"\n{info.model_name}:")
        print(f"  Max Input Tokens: {info.max_input_tokens:,}")
        print(f"  Max Output Tokens: {info.max_output_tokens:,}")


def get_max_output_tokens(model_name: str) -> int:
    """Get max output tokens with safe fallback"""
    validate_model_name(model_name)

    if model_name.startswith("lm_studio/"):
        try:
            models = get_model_list()
            for model in models.data:
                if model.id == model_name[len("lm_studio/") :]:
                    return model.max_context_length
        except Exception:
            loguru.logger.warning(f"Could not fetch LM Studio model info for {model_name}, using default")

    if model_name in model_info:
        return model_info[model_name].max_output_tokens

    try:
        return litellm_get_model_max_output_tokens(model_name)
    except Exception:
        loguru.logger.warning(f"Model {model_name} not found in LiteLLM registry, using default")
        return DEFAULT_MAX_OUTPUT_TOKENS


def get_max_input_tokens(model_name: str) -> int:
    """Get max input tokens with safe fallback"""
    validate_model_name(model_name)

    if model_name.startswith("lm_studio/"):
        try:
            models = get_model_list()
            for model in models.data:
                if model.id == model_name[len("lm_studio/") :]:
                    return model.max_context_length
        except Exception:
            loguru.logger.warning(f"Could not fetch LM Studio model info for {model_name}, using default")

    if model_name in model_info:
        return model_info[model_name].max_input_tokens

    try:
        return litellm_get_model_max_input_tokens(model_name)
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
