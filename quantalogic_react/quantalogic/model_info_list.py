from quantalogic_react.quantalogic.model_info import ModelInfo

model_info = {
    "dashscope/qwen-max": ModelInfo(
        model_name="dashscope/qwen-max",
        max_output_tokens=8 * 1024,
        max_input_tokens=32 * 1024,
    ),
    "dashscope/qwen-plus": ModelInfo(
        model_name="dashscope/qwen-plus",
        max_output_tokens=8 * 1024,
        max_input_tokens=131072,
    ),
    "dashscope/qwen-turbo": ModelInfo(
        model_name="dashscope/qwen-turbo",
        max_output_tokens=8 * 1024,
        max_input_tokens=1000000,
    ),
    "deepseek-reasoner": ModelInfo(
        model_name="deepseek-reasoner",
        max_output_tokens=8 * 1024,
        max_input_tokens=1024 * 128,
    ),
    "openrouter/deepseek/deepseek-r1": ModelInfo(
        model_name="openrouter/deepseek/deepseek-r1",
        max_output_tokens=8 * 1024,
        max_input_tokens=1024 * 128,
    ),
    "openrouter/mistralai/mistral-large-2411": ModelInfo(
        model_name="openrouter/mistralai/mistral-large-2411",
        max_output_tokens=128 * 1024,
        max_input_tokens=1024 * 128,
    ),
    "mistralai/mistral-large-2411": ModelInfo(
        model_name="mistralai/mistral-large-2411",
        max_output_tokens=128 * 1024,
        max_input_tokens=1024 * 128,
    ),
    "deepseek/deepseek-chat": ModelInfo(
        model_name="deepseek/deepseek-chat",
        max_output_tokens=8 * 1024,
        max_input_tokens=1024 * 64,
    ),
    "deepseek/deepseek-reasoner": ModelInfo(
        model_name="deepseek/deepseek-reasoner",
        max_output_tokens=8 * 1024,
        max_input_tokens=1024 * 64,
        max_cot_tokens=1024 * 32,
    ),
    "nvidia/deepseek-ai/deepseek-r1": ModelInfo(
        model_name="nvidia/deepseek-ai/deepseek-r1",
        max_output_tokens=8 * 1024,
        max_input_tokens=1024 * 64,
    ),
    "ovh/DeepSeek-R1-Distill-Llama-70B": ModelInfo(
        model_name="ovh/DeepSeek-R1-Distill-Llama-70B",
        max_output_tokens=8 * 1024,
        max_input_tokens=1024 * 64,
    ),
    "gemini/gemini-2.0-flash": ModelInfo(
        model_name="gemini/gemini-2.0-flash",
        max_input_tokens=1000000,
        max_output_tokens=8 * 1024,
        input_cost_per_token=0.0000001,
    ),
    "openrouter/google/gemini-2.0-flash-001": ModelInfo(
        model_name="openrouter/google/gemini-2.0-flash-001",
        max_input_tokens=1000000,
        max_output_tokens=8 * 1024,
        input_cost_per_token=0.0000001,
    ),
    # POE API Models
    "poe/Claude-Sonnet-4": ModelInfo(
        model_name="poe/Claude-Sonnet-4",
        max_input_tokens=200000,  # Claude's context window
        max_output_tokens=8192,   # Standard output limit
    ),
    "poe/Claude-Opus-4.1": ModelInfo(
        model_name="poe/Claude-Opus-4.1",
        max_input_tokens=200000,
        max_output_tokens=8192,
    ),
    "poe/Claude-Haiku-3.5": ModelInfo(
        model_name="poe/Claude-Haiku-3.5",
        max_input_tokens=200000,
        max_output_tokens=8192,
    ),
    "poe/Gemini-2.0-Flash": ModelInfo(
        model_name="poe/Gemini-2.0-Flash",
        max_input_tokens=1000000,  # Gemini's large context window
        max_output_tokens=8192,
    ),
    "poe/Gemini-1.5-Pro": ModelInfo(
        model_name="poe/Gemini-1.5-Pro",
        max_input_tokens=2000000,  # Gemini Pro's extended context
        max_output_tokens=8192,
    ),
    "poe/Grok-4": ModelInfo(
        model_name="poe/Grok-4",
        max_input_tokens=131072,   # Grok's context window
        max_output_tokens=8192,
    ),
    "poe/Grok-3": ModelInfo(
        model_name="poe/Grok-3",
        max_input_tokens=131072,
        max_output_tokens=8192,
    ),
    "poe/GPT-4o": ModelInfo(
        model_name="poe/GPT-4o",
        max_input_tokens=128000,   # GPT-4o context window
        max_output_tokens=16384,   # GPT-4o output limit
    ),
    "poe/o3-mini": ModelInfo(
        model_name="poe/o3-mini",
        max_input_tokens=128000,
        max_output_tokens=65536,   # o3-mini has higher output limit
    ),
    "poe/DeepSeek-R1": ModelInfo(
        model_name="poe/DeepSeek-R1",
        max_input_tokens=131072,   # DeepSeek R1 context window
        max_output_tokens=8192,
        max_cot_tokens=32768,      # DeepSeek R1 supports chain-of-thought
    ),
}
