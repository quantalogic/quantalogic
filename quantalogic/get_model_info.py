model_info = {
    "dashscope/qwen-max": {"max_output_tokens": 8 * 1024, "max_input_tokens": 32 * 1024},
    "dashscope/qwen-plus": {"max_output_tokens": 8 * 1024, "max_input_tokens": 131072},
    "dashscope/qwen-turbo": {"max_output_tokens": 8 * 1024, "max_input_tokens": 1000000},
    "deepseek-reasoner": {"max_output_tokens": 8 * 1024, "max_input_tokens": 1024 * 128},
    "openrouter/deepseek/deepseek-r1": {"max_output_tokens": 8 * 1024, "max_input_tokens": 1024 * 128},
    "openrouter/mistralai/mistral-large-2411": {"max_output_tokens": 128 * 1024, "max_input_tokens": 1024 * 128},
    "mistralai/mistral-large-2411": {"max_output_tokens": 128 * 1024, "max_input_tokens": 1024 * 128},
    "deepseek/deepseek-chat": {"max_output_tokens": 8* 1024, "max_input_tokens": 1024*64},
    "deepseek/deepseek-reasoner": {"max_output_tokens": 8* 1024, "max_input_tokens": 1024*64, "max_cot_tokens": 1024*32 },
}


def print_model_info():
    for model, info in model_info.items():
        print(f"\n{model}:")
        print(f"  Max Input Tokens: {info['max_input_tokens']:,}")
        print(f"  Max Output Tokens: {info['max_output_tokens']:,}")


if __name__ == "__main__":
    print_model_info()


def get_max_output_tokens(model_name: str) -> int | None:
    """Get the maximum output tokens for a given model name."""
    return model_info.get(model_name, {}).get("max_output_tokens", None)


def get_max_input_tokens(model_name: str) -> int | None:
    """Get the maximum input tokens for a given model name."""
    return model_info.get(model_name, {}).get("max_input_tokens", None)


def get_max_tokens(model_name: str) -> int | None:
    """Get the maximum total tokens (input + output) for a given model name."""
    model_data = model_info.get(model_name, {})
    max_input = model_data.get("max_input_tokens")
    max_output = model_data.get("max_output_tokens")

    if max_input is None or max_output is None:
        return None

    return max_input + max_output
