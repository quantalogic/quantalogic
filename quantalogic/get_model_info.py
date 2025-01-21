model_info = {
    "deepseek-reasoner": {"max_output_tokens": 8 * 1024, "max_input_tokens": 1024 * 128},
    "openrouter/deepseek/deepseek-r1": {"max_output_tokens": 8 * 1024, "max_input_tokens": 1024 * 128},
}


def get_max_output_tokens(model_name: str) -> int | None:
    """Get the maximum output tokens for a given model name."""
    return model_info.get(model_name, {}).get("max_output_tokens", None)


def get_max_input_tokens(model_name: str) -> int | None:
    """Get the maximum input tokens for a given model name."""
    return model_info.get(model_name, {}).get("max_input_tokens", None)
